"""Restartable, segmented PUBLIC sampling for a stable external Linux host.

Never submits venue orders or claims exchange fill evidence. Session IDs are
immutable directories; interrupted segments require explicit preservation.
"""
import argparse
import fcntl
import os
from pathlib import Path
import re
import subprocess
import time

from research.phase3.polybot_sdk.collector import collect, TradeWatermark
from research.phase3.polybot_sdk.model import decode, dumps
from research.phase3.polybot_sdk.runtime import private_write
from research.phase4.audit import audit_capture, inspect_session, VENUES, DAY_MS

ROOT = Path(__file__).resolve().parents[2]


def current_clean_commit():
    try:
        sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True,
                             capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],
                               cwd=ROOT, check=True, capture_output=True,
                               text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError('Stable committed Git checkout required') from exc
    if not re.fullmatch('[0-9a-f]{40}', sha) or dirty:
        raise ValueError('Refusing dirty or unpinned source checkout')
    return sha


def _write_atomic(path, payload):
    """Replace only the operator status report; never rewrite sealed segments."""
    temp = path.with_name('.' + path.name + '.temporary-' + str(os.getpid()))
    with temp.open('x', encoding='utf-8') as handle:
        os.chmod(temp, 0o600)
        handle.write(dumps(payload) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    dirfd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)


def _recovery_event(path, item):
    with path.open('a', encoding='utf-8') as file:
        os.chmod(path, 0o600)
        file.write(dumps(item) + '\n')
        file.flush()
        os.fsync(file.fileno())


def run_capture(directory, *, symbol='BTCUSDT', days=7, segment_seconds=900,
                interval=5, max_new_segments=None, quarantine_incomplete=False,
                source_revision=None):
    if (not isinstance(days, int) or not 1 <= days <= 365
            or not isinstance(segment_seconds, int) or not 5 <= segment_seconds <= 86400
            or not isinstance(interval, int) or not 1 <= interval <= 60
            or not re.fullmatch('[A-Z0-9]{3,20}USDT', symbol)
            or max_new_segments is not None and (not isinstance(max_new_segments, int)
                                                   or max_new_segments < 1)):
        raise ValueError('Invalid frozen capture configuration')
    source_revision = current_clean_commit() if source_revision is None else source_revision
    if not re.fullmatch('[0-9a-f]{40}', source_revision):
        raise ValueError('Source revision must be a 40-character Git SHA')

    root = Path(directory).resolve()
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (root / '.capture.lock').open('a+') as lock:
        os.chmod(root / '.capture.lock', 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Capture directory already has an active recorder') from exc
        plan_path = root / 'plan.json'
        config = {'schema': 1, 'mode': 'PUBLIC_RECORD_ONLY', 'symbol': symbol, 'days': days,
                  'segmentSeconds': segment_seconds, 'interval': interval,
                  'sourceRevision': source_revision, 'liveAllowed': False}
        if plan_path.exists():
            plan = decode(plan_path.read_text(encoding='utf-8'))
            if {k: plan.get(k) for k in config} != config:
                raise ValueError('Frozen capture plan differs; use a NEW directory')
        else:
            if any(root.iterdir()) and set(p.name for p in root.iterdir()) != {'.capture.lock'}:
                raise ValueError('Nonempty uninitialized capture directory')
            plan = {**config, 'startedAtMs': int(time.time() * 1000)}
            private_write(plan_path, plan)

        segments_root = root / 'segments'
        archive = root / 'interrupted'
        segments_root.mkdir(mode=0o700, exist_ok=True)
        archive.mkdir(mode=0o700, exist_ok=True)
        completed = []
        next_index = 1
        seen_recovery = (root / 'recovery.jsonl').exists()
        for entry in sorted(segments_root.iterdir()):
            match = re.fullmatch(r'segment-(\d{6})', entry.name)
            if not match or not entry.is_dir():
                raise ValueError('Unexpected file in immutable segment directory')
            index = int(match[1])
            next_index = max(next_index, index + 1)
            report_path = entry / 'report.json'
            if not report_path.exists():
                complete = False
            else:
                report = decode(report_path.read_text(encoding='utf-8'))
                complete = report.get('complete') is True
            if not complete:
                if not quarantine_incomplete:
                    raise ValueError('Interrupted segment: use --quarantine-incomplete to retain evidence and continue')
                preserved = archive / entry.name
                if preserved.exists():
                    raise ValueError('Archive name conflict')
                os.rename(entry, preserved)
                _recovery_event(root / 'recovery.jsonl', {
                    'segment': entry.name, 'observedAtMs': int(time.time() * 1000),
                    'action': 'PRESERVED_INTERRUPTED_SEGMENT', 'qualification': 'NO_GO'})
                seen_recovery = True
                continue
            details = inspect_session(entry)
            if details['sourceRevision'] != source_revision or details['initialWatermarks'] is None:
                raise ValueError('Cannot resume unpinned or legacy capture segment')
            completed.append((entry, details))
        if not completed:
            current = {v: TradeWatermark().snapshot() for v in VENUES}
        else:
            current = completed[-1][1]['finalWatermarks']

        new_segments = 0
        first_full_utc_ms = ((int(plan['startedAtMs']) + DAY_MS - 1) // DAY_MS) * DAY_MS
        deadline = first_full_utc_ms + days * DAY_MS
        while int(time.time() * 1000) < deadline:
            if max_new_segments is not None and new_segments >= max_new_segments:
                break
            remaining = (deadline - int(time.time() * 1000)) / 1000
            # Avoid an unbounded trailing session or zero-length session.
            if remaining < .01:
                break
            segment_length = min(segment_seconds, remaining)
            target = segments_root / ('segment-%06d' % next_index)
            if target.exists():
                raise ValueError('Refusing to overwrite existing segment')
            collect(target, seconds=segment_length, interval=interval, symbol=symbol,
                    initial_watermarks=current, source_revision=source_revision)
            details = inspect_session(target)
            if details['initialWatermarks'] != current:
                raise ValueError('Watermark recovery mismatch after capture')
            completed.append((target, details))
            current = details['finalWatermarks']
            next_index += 1
            new_segments += 1

        if not completed:
            return {'status': 'NO_COMPLETE_SEGMENTS', 'decision': 'NO_GO',
                    'liveAllowed': False}
        report = audit_capture([p for p, _ in completed], min_days=days)
        if seen_recovery:
            report['issues'] = sorted(set(report['issues'] + ['RECOVERED_INTERRUPTED_SEGMENT']))
            report['continuousSamplingWindow'] = False
        report['frozenPlan'] = config
        report['newSegments'] = new_segments
        report['finishedTargetWallWindow'] = int(time.time() * 1000) >= deadline
        report['qualifiesCompleteMarketTape'] = False
        report['phase4Complete'] = False
        report['decision'] = 'NO_GO'
        _write_atomic(root / 'latest-audit.json', report)
        return report


def main():
    parser = argparse.ArgumentParser(description='PAPER-only segmented PUBLIC sampling recorder')
    parser.add_argument('--root', required=True, help='Persistent output directory, never a repo-tracked path')
    parser.add_argument('--symbol', default='BTCUSDT')
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--segment-seconds', type=int, default=900)
    parser.add_argument('--interval', type=int, default=5)
    parser.add_argument('--max-new-segments', type=int, default=None,
                        help='Stop early for operator checks; never marks capture complete')
    parser.add_argument('--quarantine-incomplete', action='store_true',
                        help='Preserve interrupted data under interrupted/ and keep NO_GO')
    opts = parser.parse_args()
    print(dumps(run_capture(opts.root, symbol=opts.symbol, days=opts.days,
                            segment_seconds=opts.segment_seconds, interval=opts.interval,
                            max_new_segments=opts.max_new_segments,
                            quarantine_incomplete=opts.quarantine_incomplete)))


if __name__ == '__main__':
    main()
