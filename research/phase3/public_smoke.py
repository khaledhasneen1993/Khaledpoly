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
from research.phase3.polybot_sdk.model import dumps
from research.phase3.polybot_sdk.runtime import private_write, shadow_run, replay_shadow


def main():
    output = ROOT / 'research/output/phase3-public'
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
    signal_process, server = None, None
    try:
        with (output / 'executor.log').open('x') as logs:
            server = subprocess.Popen(args, env=environment, cwd=ROOT, stdout=logs, stderr=subprocess.STDOUT)
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
                report = shadow_run(client, output / 'shadow', seconds=45, interval=1)
                signal_status = signal_process.wait(timeout=30)
            parity = replay_shadow(output / 'shadow', output / 'replay.json')
            latest = client.snapshot()
            fresh_books = sum(int(latest['generatedMs']) - int(book['sourceMs']) < int(latest['maxBookAgeMs']) for book in latest['books'].values())
            result = {'scope': 'PUBLIC_INTEGRATION_SMOKE_NOT_QUALIFICATION', 'snapshots': report['snapshots'],
                      'markets': len(latest['markets']), 'freshBooks': fresh_books,
                      'signalCollectorExit': signal_status, 'replayStatus': parity['status'],
                      'decision': 'NO_GO', 'liveAllowed': False, 'newStrategiesExecuted': False,
                      'status': 'PUBLIC_BOOKS_OBSERVED' if fresh_books and latest['markets'] else 'INCOMPLETE_PUBLIC_COVERAGE'}
            private_write(output / 'summary.json', result)
            print(dumps(result))
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
