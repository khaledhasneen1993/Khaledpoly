"""Fail-closed integrity audit for independent PUBLIC research sampling sessions.

This verifies recorded coverage and integrity; it never promotes strategies,
treats REST samples as a complete tape, or runs venue orders.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from research.phase3.polybot_sdk.model import decode, integer
from research.phase3.polybot_sdk.collector import _sha256_file
from research.phase3.polybot_sdk.runtime import private_write

VENUES = ('binance-spot', 'bybit-spot')
DAY_MS = 86400000


def _read_json(path):
    return decode(Path(path).read_text(encoding='utf-8'))


def inspect_session(directory):
    """Validate one CLOSED segment. Never infer missing records from silence."""
    root = Path(directory)
    manifest = _read_json(root / 'manifest.json')
    report = _read_json(root / 'report.json')
    if (manifest.get('schema') not in (2, 3, 4) or manifest.get('mode') != 'PUBLIC_RECORD_ONLY'
            or manifest.get('liveAllowed') is not False or not isinstance(manifest.get('symbol'), str)
            or manifest.get('coverage') != 'SAMPLED'
            or report.get('complete') is not True or report.get('coverage') != 'SAMPLED'
            or report.get('completeTradeTape') is not False
            or report.get('sevenDayHoldoutQualified') is not False
            or report.get('decision') != 'NO_GO' or report.get('liveAllowed') is not False):
        raise ValueError('Incomplete, unsupported or falsely qualified capture')
    start, end = integer(manifest['startedAtMs']), integer(report['endedAtMs'])
    elapsed = integer(report['elapsedMonotonicMs'])
    if start != integer(report['startedAtMs']) or start <= 0 or end < start or elapsed <= 0:
        raise ValueError('Invalid capture clock or boundary')
    if abs((end - start) - elapsed) > 30000:
        raise ValueError('Capture wall/monotonic clock drift exceeds 30 seconds')

    initial_state, final_state = None, None
    initial_retry, final_retry = None, None
    if manifest['schema'] in (3, 4):
        from research.phase3.polybot_sdk.collector import TradeWatermark
        initial_state, final_state = {}, {}
        for venue in VENUES:
            initial_state[venue] = TradeWatermark.restore(manifest['initialWatermarks'][venue]).snapshot()
            final_state[venue] = TradeWatermark.restore(report['finalWatermarks'][venue]).snapshot()
        if not isinstance(manifest.get('sourceRevision'), (str, type(None))):
            raise ValueError('Invalid capture revision')
    if manifest['schema'] == 4:
        from research.phase3.polybot_sdk.collector import normalize_poll_state
        initial_retry, final_retry = {}, {}
        for venue in VENUES:
            initial_retry[venue] = normalize_poll_state(manifest['initialPollStates'][venue])
            final_retry[venue] = normalize_poll_state(report['finalPollStates'][venue])
    for name in ('public.jsonl', 'features.jsonl'):
        expected = report['fileSha256'][name]
        if not isinstance(expected, str) or len(expected) != 64 or _sha256_file(root / name) != expected:
            raise ValueError('Capture content hash mismatch: ' + name)

    counts = {v: Counter() for v in VENUES}
    latest = {v: None for v in VENUES}
    first = {v: None for v in VENUES}
    last_success = {v: None for v in VENUES}
    first_success = {v: None for v in VENUES}
    large_gap_ms = {v: 0 for v in VENUES}
    large_success_gap_ms = {v: 0 for v in VENUES}
    public_count = 0
    with (root / 'public.jsonl').open(encoding='utf-8') as stream:
        for raw in stream:
            if len(raw) > 2 * 1024 * 1024 + 4096 or not raw.endswith('\n'):
                raise ValueError('Invalid public audit row boundary')
            row = decode(raw)
            venue, status = row.get('venue'), row.get('status')
            if venue not in VENUES or row.get('symbol') != manifest['symbol']:
                raise ValueError('Invalid public venue/symbol identity')
            stamp = integer(row['polledMs'])
            if not start - 1000 <= stamp <= end + 1000:
                raise ValueError('Public event outside capture interval')
            if latest[venue] is not None:
                if stamp < latest[venue]:
                    raise ValueError('Public event availability clock regression')
                large_gap_ms[venue] = max(large_gap_ms[venue], stamp - latest[venue])
            else:
                first[venue] = stamp
            latest[venue] = stamp
            public_count += 1
            if status == 'SAMPLED_PUBLIC_TRADES':
                counts[venue]['sampledPolls'] += 1
                if last_success[venue] is None:
                    first_success[venue] = stamp
                else:
                    large_success_gap_ms[venue] = max(
                        large_success_gap_ms[venue], stamp - last_success[venue])
                last_success[venue] = stamp
                if row.get('coverage') != 'SAMPLED_NOT_COMPLETE_TRADE_TAPE':
                    raise ValueError('Public sample misidentified as complete tape')
                # Recheck payload fingerprint, separately from file-level integrity.
                from research.phase3.polybot_sdk.features import fingerprint
                if fingerprint(row['payload']) != row.get('payloadSha256'):
                    raise ValueError('Public source payload fingerprint mismatch')
                for key in ('uniqueTrades', 'duplicateTrades', 'olderTrades'):
                    if integer(row.get(key, -1)) < 0:
                        raise ValueError('Invalid sample event metrics')
                counts[venue]['featureRows'] += integer(row['uniqueTrades'])
                counts[venue]['duplicateTrades'] += integer(row['duplicateTrades'])
                counts[venue]['olderTrades'] += integer(row['olderTrades'])
            elif status == 'BACKOFF':
                counts[venue]['backoffPolls'] += 1
            elif status in ('HTTP_BACKOFF', 'NETWORK_GAP', 'RATE_LIMIT'):
                counts[venue]['errorPolls'] += 1
            else:
                raise ValueError('Unknown public recorder state: ' + str(status))
            if row.get('sourceAccessBlocked') is True:
                counts[venue]['sourceAccessBlocked'] = 1

    if public_count == 0 or any(first[v] is None for v in VENUES):
        raise ValueError('Missing per-venue polling records')
    feature_count = 0
    with (root / 'features.jsonl').open(encoding='utf-8') as stream:
        for raw in stream:
            if len(raw) > 65536 or not raw.endswith('\n'):
                raise ValueError('Invalid feature row boundary')
            from research.phase3.polybot_sdk.features import Observation
            feature = Observation.parse(decode(raw))
            if feature.venue not in VENUES or feature.symbol != manifest['symbol']:
                raise ValueError('Feature belongs to a different source')
            feature_count += 1
    if feature_count != integer(report['featureRows']):
        raise ValueError('Feature row count mismatch')
    for venue in VENUES:
        metrics = report['perVenue'][venue]
        for key in ('sampledPolls', 'backoffPolls', 'errorPolls',
                    'featureRows', 'duplicateTrades', 'olderTrades'):
            if integer(metrics[key]) != counts[venue][key]:
                raise ValueError('Per-venue accounting mismatch: ' + venue + '/' + key)
        if bool(metrics['sourceAccessBlocked']) != bool(counts[venue]['sourceAccessBlocked']):
            raise ValueError('Source access evidence mismatch')
    if feature_count != sum(counts[v]['featureRows'] for v in VENUES):
        raise ValueError('Source feature total mismatch')
    return {'directory': str(root), 'startedAtMs': start, 'endedAtMs': end,
            'initialWatermarks': initial_state, 'finalWatermarks': final_state,
            'initialPollStates': initial_retry, 'finalPollStates': final_retry,
            'sourceRevision': manifest.get('sourceRevision'),
            'intervalSeconds': manifest['interval'], 'symbol': manifest['symbol'],
            'perVenue': {v: {'sampledPolls': counts[v]['sampledPolls'],
                              'backoffPolls': counts[v]['backoffPolls'],
                              'errorPolls': counts[v]['errorPolls'],
                              'featureRows': counts[v]['featureRows'],
                              'sourceAccessBlocked': bool(counts[v]['sourceAccessBlocked']),
                              'firstPollMs': first[v], 'lastPollMs': latest[v],
                              'firstSuccessfulSampleMs': first_success[v],
                              'lastSuccessfulSampleMs': last_success[v],
                              'largestSuccessfulSampleGapMs': large_success_gap_ms[v],
                              'largestInternalPollGapMs': large_gap_ms[v]} for v in VENUES}}


def audit_capture(directories, min_days=7, max_poll_gap_ms=300000):
    """Audit sessions supplied explicitly; never discover or overwrite them."""
    if not 1 <= min_days <= 365 or not 1000 <= max_poll_gap_ms <= DAY_MS:
        raise ValueError('Invalid capture audit requirements')
    paths = [Path(p).resolve() for p in directories]
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('Capture input must contain unique, explicit sessions')
    sessions = sorted((inspect_session(p) for p in paths), key=lambda r: r['startedAtMs'])
    issues = []
    for i, item in enumerate(sessions):
        if item['symbol'] != sessions[0]['symbol']:
            issues.append('MIXED_MARKET_SYMBOLS')
        if item['initialWatermarks'] is None or item['finalWatermarks'] is None:
            issues.append('UNVERIFIED_WATERMARK_CONTINUITY')
        if item['initialPollStates'] is None or item['finalPollStates'] is None:
            issues.append('UNVERIFIED_BACKOFF_CONTINUITY')
        if i and item['initialPollStates'] != sessions[i-1]['finalPollStates']:
            issues.append('RETRY_BACKOFF_DISCONTINUITY')
        if i and (item['initialWatermarks'] != sessions[i-1]['finalWatermarks']):
            issues.append('WATERMARK_DISCONTINUITY')
        if item['sourceRevision'] is None:
            issues.append('UNPINNED_SOURCE_REVISION')
        elif i and item['sourceRevision'] != sessions[0]['sourceRevision']:
            issues.append('SOURCE_REVISION_CHANGED')
        if i and item['startedAtMs'] < sessions[i-1]['endedAtMs']:
            issues.append('OVERLAPPING_SESSIONS')
        elif i and item['startedAtMs'] - sessions[i-1]['endedAtMs'] > max_poll_gap_ms:
            issues.append('INTER_SESSION_GAP')
        for venue in VENUES:
            stats = item['perVenue'][venue]
            if stats['largestInternalPollGapMs'] > max_poll_gap_ms:
                issues.append(venue + ':LONG_POLL_GAP')
            if stats['sampledPolls'] == 0:
                issues.append(venue + ':NO_SUCCESSFUL_SAMPLES')
            else:
                if stats['firstSuccessfulSampleMs'] - item['startedAtMs'] > max_poll_gap_ms:
                    issues.append(venue + ':INITIAL_SUCCESS_GAP')
                if item['endedAtMs'] - stats['lastSuccessfulSampleMs'] > max_poll_gap_ms:
                    issues.append(venue + ':TERMINAL_SUCCESS_GAP')
                if stats['largestSuccessfulSampleGapMs'] > max_poll_gap_ms:
                    issues.append(venue + ':SUCCESS_SAMPLING_GAP')
            if stats['sourceAccessBlocked']:
                issues.append(venue + ':SOURCE_ACCESS_BLOCKED')
            if i:
                prev = sessions[i-1]['perVenue'][venue]
                gap = stats['firstPollMs'] - prev['lastPollMs']
                if gap > max_poll_gap_ms:
                    issues.append(venue + ':INTER_SESSION_POLL_GAP')
                if stats['firstSuccessfulSampleMs'] is not None and prev['lastSuccessfulSampleMs'] is not None:
                    if stats['firstSuccessfulSampleMs'] - prev['lastSuccessfulSampleMs'] > max_poll_gap_ms:
                        issues.append(venue + ':INTER_SESSION_SUCCESS_GAP')
    wall_span = sessions[-1]['endedAtMs'] - sessions[0]['startedAtMs']
    # A rolling 7*24h interval is NOT seven complete UTC calendar days.
    first_full_utc_ms = ((sessions[0]['startedAtMs'] + DAY_MS - 1) // DAY_MS) * DAY_MS
    full_utc_days = max(0, (sessions[-1]['endedAtMs'] - first_full_utc_ms) // DAY_MS)
    if wall_span < min_days * DAY_MS or full_utc_days < min_days:
        issues.append('INSUFFICIENT_CAPTURE_DAYS')
    issues = sorted(set(issues))
    return {'schema': 1, 'scope': 'PHASE4_PUBLIC_REST_SAMPLING_AUDIT',
            'sessions': len(sessions), 'symbol': sessions[0]['symbol'],
            'startedAtMs': sessions[0]['startedAtMs'], 'endedAtMs': sessions[-1]['endedAtMs'],
            'wallSpanDays': round(wall_span / DAY_MS, 4), 'fullUtcDays': full_utc_days,
            'firstFullUtcDayMs': first_full_utc_ms, 'requiredDays': min_days,
            'issues': issues, 'continuousSamplingWindow': not issues,
            'completeTradeTape': False, 'venueFillEvidence': False,
            'strategyQualified': False, 'phase4Complete': False,
            'decision': 'NO_GO', 'liveAllowed': False}


def main():
    parser = argparse.ArgumentParser(description='Audit phase-four recorded PUBLIC REST samples only')
    parser.add_argument('sessions', nargs='+', help='Directories with immutable capture reports')
    parser.add_argument('--output', required=True, help='New, never-overwritten audit JSON file')
    parser.add_argument('--required-days', type=int, default=7)
    parser.add_argument('--max-poll-gap-ms', type=int, default=300000)
    args = parser.parse_args()
    report = audit_capture(args.sessions, args.required_days, args.max_poll_gap_ms)
    private_write(args.output, report)
    from research.phase3.polybot_sdk.model import dumps
    print(dumps(report))


if __name__ == '__main__':
    main()
