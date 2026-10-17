"""Independent Phase-4 CEX/Polymarket clock and evidence gate.

A passing *capture* gate is not market, settlement, or strategy acceptance.
Never infer fills, oracle truth, or profitability from PUBLIC depth.
"""
import argparse
from pathlib import Path

from research.phase3.polybot_sdk.model import decode, dumps, integer
from research.phase3.polybot_sdk.runtime import private_write
from research.phase4.audit import audit_capture, DAY_MS


def tape_bounds(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 2:
        raise ValueError('Empty or missing Polymarket journal')
    with path.open('rb') as stream:
        first = stream.readline(65537)
        if not first.endswith(b'\n') or len(first) > 65536:
            raise ValueError('Invalid first journal boundary')
        stream.seek(max(0, path.stat().st_size - 65536))
        lines = [line for line in stream.read().split(b'\n') if line]
    if not lines:
        raise ValueError('Missing last journal record')
    last = lines[-1]
    if len(last) > 65536:
        raise ValueError('Unbounded last journal record')
    a, b = decode(first), decode(last)
    start, end = integer(a['arrivalMs']), integer(b['arrivalMs'])
    if start <= 0 or end < start:
        raise ValueError('Invalid Polymarket journal timestamps')
    return start, end


def evaluate(cex_dirs, polymarket_tapes, days=7, max_gap_ms=300000):
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError('Invalid prospective acceptance duration')
    if not cex_dirs or not polymarket_tapes:
        raise ValueError('Both independent CEX and Polymarket tapes are required')
    # This function re-inspects original files, not operator-authored reports.
    cex = audit_capture(cex_dirs, min_days=days, max_poll_gap_ms=max_gap_ms)
    from research.phase2.inspect_recording import inspect
    clob = []
    for raw_path in polymarket_tapes:
        path = Path(raw_path).resolve()
        report = inspect(path)
        first, last = tape_bounds(path)
        clob.append({'path': str(path), 'startMs': first, 'endMs': last,
                     'complete': report['recordingClosedCleanly'],
                     'gaps': report['gapReasons'], 'errors': report['errors'],
                     'format': report['frameAtomicity'],
                     'rawFrames': report['events'].get('RAW_MARKET', 0),
                     'books': report['normalizedEvents'].get('BOOK', 0)})
    clob.sort(key=lambda x: x['startMs'])
    issues = list(cex['issues'])
    for i, tape in enumerate(clob):
        if not tape['complete']:
            issues.append('POLYMARKET_INCOMPLETE_TAPE')
        if tape['errors'] or tape['gaps']:
            issues.append('POLYMARKET_SOURCE_GAPS_OR_ERRORS')
        if tape['format'] != 'recorded-frame-v1' or tape['rawFrames'] < 1 or tape['books'] < 1:
            issues.append('POLYMARKET_FRAME_DEPTH_EVIDENCE_MISSING')
        if i:
            if tape['startMs'] < clob[i-1]['endMs']:
                issues.append('POLYMARKET_OVERLAPPING_RUNS')
            if tape['startMs'] - clob[i-1]['endMs'] > max_gap_ms:
                issues.append('POLYMARKET_INTER_RUN_GAP')
    common_start = max(cex['startedAtMs'], clob[0]['startMs'])
    common_end = min(cex['endedAtMs'], clob[-1]['endMs'])
    first_midnight = ((common_start + DAY_MS - 1) // DAY_MS) * DAY_MS
    full_overlap_days = max(0, (common_end - first_midnight) // DAY_MS)
    if full_overlap_days < days:
        issues.append('INSUFFICIENT_OVERLAPPING_FULL_UTC_DAYS')
    issues = sorted(set(issues))
    return {'schema':1, 'scope':'PHASE4_INDEPENDENT_PUBLIC_CAPTURE_GATE',
            'cexSessions':cex['sessions'], 'polymarketTapes':len(clob),
            'commonFullUtcDays':full_overlap_days,
            'requiredDays':days, 'issues':issues,
            'publicCaptureGatePassed':not issues,
            'marketUniverseAndSettlementEvidenceVerified':False,
            'venueFillEvidence':False, 'strategyQualified':False,
            'phase4Complete':False, 'decision':'NO_GO', 'liveAllowed':False}


def main():
    parser=argparse.ArgumentParser(description='Audit independent CEX + CLOB tapes (PAPER, no orders)')
    parser.add_argument('--cex',nargs='+',required=True,help='Sealed PUBLIC REST capture session directories')
    parser.add_argument('--polymarket',nargs='+',required=True,help='Recorded raw/normalized CLOB events.jsonl tapes')
    parser.add_argument('--output',required=True)
    parser.add_argument('--days',type=int,default=7)
    args=parser.parse_args()
    result=evaluate(args.cex,args.polymarket,args.days)
    private_write(args.output,result)
    print(dumps(result))


if __name__=='__main__':
    main()
