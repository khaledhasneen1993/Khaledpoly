"""Bounded public integration capture for CI, using a disposable virtual PAPER account."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.phase3.polybot_sdk.client import PaperClient
from research.phase3.polybot_sdk.model import dumps, decode
from research.phase3.polybot_sdk.runtime import private_write, shadow_run, replay_shadow


def compare_action_audits(first, second):
    # JSON object property order is unspecified across independently started JVMs.
    # Compare every action/value in receive order, while retaining bounded streaming reads.
    from itertools import zip_longest
    with Path(first).open() as left, Path(second).open() as right:
        for first_row, second_row in zip_longest(left, right):
            if first_row is None or second_row is None or decode(first_row) != decode(second_row):
                raise ValueError('External PAPER action audit mismatch')


def main():
    execution_mode = '--execute-paper' in sys.argv[1:]
    output = ROOT / ('research/output/phase3-public-execution' if execution_mode else 'research/output/phase3-public')
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    environment = {k: v for k, v in os.environ.items() if not k.startswith('POLYMARKET_')}
    environment['POLYBOT_EXECUTOR_TOKEN'] = secrets.token_urlsafe(32)
    args = ['java', '-jar', str(ROOT / 'executor-service/target/executor-service-0.0.1-SNAPSHOT.jar'),
            '--server.port=18083', '--server.address=127.0.0.1', '--hft.mode=PAPER', '--hft.events.enabled=false',
            '--executor.sim.enabled=true', '--paper.closed-loop.enabled=true', '--paper.phase3.enabled=true',
            '--paper.market-data.enabled=true', '--hft.polymarket.market-ws-enabled=true',
            '--hft.strategy.gabagool.enabled=false', '--spring.application.name=phase3-public',
            '--paper.closed-loop.config=' + str(ROOT / 'research/phase2/research-config.json'),
            '--executor.account.state-path=' + str(output / 'state/account.json'),
            '--paper.record.directory=' + str(output / 'ingestor'),
            '--paper.record.revision=' + environment.get('GITHUB_SHA', 'local-uncommitted')]
    if execution_mode:
        args.extend(['--paper.phase3.execution.enabled=true', '--paper.phase3.discovery.tags=politics,sports'])
    signal_process, server = None, None
    try:
        with (output / 'executor.log').open('x') as logs:
            server = subprocess.Popen(args, env=environment, cwd=ROOT, stdout=logs, stderr=subprocess.STDOUT)
            if execution_mode:
                from research.phase3.polybot_sdk.execution import PaperExecutionClient, execute_paper
                client = PaperExecutionClient('http://127.0.0.1:18083', environment['POLYBOT_EXECUTOR_TOKEN'])
            else:
                client = PaperClient('http://127.0.0.1:18083', environment['POLYBOT_EXECUTOR_TOKEN'])
            deadline, snapshot = time.monotonic() + 45, None
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError('PAPER server exited; inspect executor.log')
                try:
                    snapshot = client.snapshot()
                    break
                except (HTTPError, URLError, ValueError, TimeoutError):
                    time.sleep(.5)
            if snapshot is None:
                raise RuntimeError('PAPER snapshot readiness failed; inspect executor.log')
            private_write(output / 'first-snapshot.json', snapshot)
            with (output / 'signals.log').open('x') as signal_log:
                signal_process = subprocess.Popen([sys.executable, '-m', 'research.phase3', 'collect-signals',
                    '--seconds', '30', '--output', str(output / 'signals')], cwd=ROOT, stdout=signal_log, stderr=subprocess.STDOUT)
                feature_path = output / 'signals/features.jsonl'
                feature_deadline = time.monotonic() + 5
                while not feature_path.exists() and signal_process.poll() is None and time.monotonic() < feature_deadline:
                    time.sleep(.1)
                if execution_mode:
                    execution_report = execute_paper(client, output / 'execution', seconds=30, interval=.5,
                                                     feature_path=feature_path if feature_path.exists() else None)
                report = shadow_run(client, output / 'shadow', seconds=45, interval=1,
                                    feature_path=feature_path if feature_path.exists() else None)
                signal_status = signal_process.wait(timeout=30)
            parity = replay_shadow(output / 'shadow', output / 'replay.json')
            latest = client.snapshot()
            fresh_books = sum(int(latest['generatedMs']) - int(book['sourceMs']) < int(latest['maxBookAgeMs']) for book in latest['books'].values())
            venue_counts = {'binance-spot': 0, 'bybit-spot': 0}
            with (output / 'signals/features.jsonl').open() as feature_stream:
                for line in feature_stream:
                    row = decode(line)
                    venue_counts[row['venue']] += 1
            signal_report = decode((output / 'signals/report.json').read_text())
            from research.phase4.audit import inspect_session
            inspect_session(output / 'signals')  # Validate actual public tape hashes, clocks and per-venue metrics.
            result = {'scope': 'PUBLIC_INTEGRATION_SMOKE_NOT_QUALIFICATION', 'snapshots': report['snapshots'],
                      'markets': len(latest['markets']), 'freshBooks': fresh_books,
                      'signalCollectorExit': signal_status, 'signalRowsByVenue': venue_counts, 'signalErrors': signal_report['errors'],
                      'phase4CaptureIntegrity': 'PASS', 'replayStatus': parity['status'],
                      'decision': 'NO_GO', 'liveAllowed': False, 'paperExecutionMode': execution_mode,
                      'newStrategiesExecuted': execution_mode and execution_report['receipts'].get('PAPER_SUBMITTED', 0) > 0,
                      'observedPaperAccount': latest['account'] if execution_mode else None,
                      'paperStatistics': latest.get('paperStatistics'),
                      'virtualExecutionReceipts': execution_report['receipts'] if execution_mode else None,
                      'status': ('PUBLIC_OBSERVATIONS_RECORDED' if fresh_books and latest['markets'] and all(venue_counts.values())
                                 else 'PARTIAL_PUBLIC_INTEGRATION')}
            private_write(output / 'summary.json', result)
            print(dumps(result))
        if execution_mode:
            server.terminate()
            server.wait(timeout=15)
            tapes = list((output / 'ingestor').glob('*/events.jsonl'))
            if len(tapes) != 1:
                raise ValueError('Expected exactly one virtual executor tape')
            from research.phase3.polybot_sdk.labels import build_labels
            labels = build_labels(tapes[0], output / 'labels')
            reports = {}
            for mode, flags in (('normalized', []), ('raw', ['--raw'])):
                replay_dir = output / ('execution-replay-' + mode)
                subprocess.run(['java', '-Dloader.main=com.polybot.hft.executor.replay.ClosedLoopMain',
                    '-cp', str(ROOT / 'executor-service/target/executor-service-0.0.1-SNAPSHOT.jar'),
                    'org.springframework.boot.loader.launch.PropertiesLauncher', str(tapes[0]), str(replay_dir),
                    str(ROOT / 'research/phase2/research-config.json'), '--external-paper', *flags], check=True)
                reports[mode] = decode((replay_dir / 'report.json').read_text())
            normalized = {k: v for k, v in reports['normalized'].items() if k != 'inputFormat'}
            raw = {k: v for k, v in reports['raw'].items() if k != 'inputFormat'}
            if normalized != raw:
                raise ValueError('External PAPER raw/normalized report mismatch')
            compare_action_audits(output / 'execution-replay-normalized/audit.jsonl',
                                  output / 'execution-replay-raw/audit.jsonl')
            result['executionReplayParity'] = 'MATCH_REPORT_AND_ACTION_AUDIT'
            result['executionReplay'] = {k: reports['normalized'][k] for k in
                                        ('cash', 'netRealizedPnl', 'dataGaps', 'decision', 'recordingClosedCleanly')}
            result['executionLabels'] = labels
            private_write(output / 'execution-verification.json', result)
            print(dumps({'executionVerification': result}))
    finally:
        for process in (signal_process, server):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
