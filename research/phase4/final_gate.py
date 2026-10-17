"""Independent Phase-4 CEX/Polymarket clock and evidence gate.

A passing *capture* gate is not market, settlement, or strategy acceptance.
Never infer fills, oracle truth, or profitability from PUBLIC depth.
"""
import argparse
from pathlib import Path

from research.phase3.polybot_sdk.model import decode, dumps, integer
from research.phase3.polybot_sdk.runtime import private_write
from research.phase4.audit import audit_capture, DAY_MS
from research.phase3.polybot_sdk.tapes import open_tape


def journal_stats(path):
    """Stream recorded CLOB tape; reject hidden gaps even when the ends match.

    Uses constant memory, checks the *actual* source RAW_MARKET event arrival
    clock, and does not equate heartbeat or RUN_END with market data freshness.
    """
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 2:
        raise ValueError('Empty or missing Polymarket journal')
    first, last, first_market, last_market, max_market_gap = None, None, None, None, 0
    entries, market_records = 0, 0
    with open_tape(path,'rb') as stream:
        while raw := stream.readline(8 * 1024 * 1024 + 1):
            if len(raw) > 8 * 1024 * 1024 or not raw.endswith(b'\n'):
                raise ValueError('Unterminated/oversized Polymarket journal row')
            item = decode(raw)
            stamp = integer(item['arrivalMs'])
            if stamp <= 0 or (last is not None and stamp < last):
                raise ValueError('Polymarket receive clock regressed or invalid')
            if first is None:
                first = stamp
            last, entries = stamp, entries + 1
            if item.get('kind') == 'RAW_MARKET':
                if first_market is None:
                    first_market = stamp
                else:
                    max_market_gap = max(max_market_gap, stamp - last_market)
                last_market = stamp
                market_records += 1
    if first is None:
        raise ValueError('Empty Polymarket journal')
    if first_market is not None:
        max_market_gap = max(max_market_gap, first_market - first,
                             last - last_market)
    return {'firstMs': first, 'lastMs': last, 'firstRawMarketMs': first_market,
            'lastRawMarketMs': last_market, 'largestRawMarketGapMs': max_market_gap,
            'rawMarketRecords': market_records, 'journalRows': entries}


def window_health(path, start, end):
    """Count source faults only in the prospective common window; audit full tape separately."""
    from collections import Counter
    excluded = Counter()
    first = last = None
    largest = errors = outside_errors = 0
    with open_tape(path,'rb') as stream:
        while raw := stream.readline(8*1024*1024+1):
            if len(raw)>8*1024*1024 or not raw.endswith(b'\n'):
                raise ValueError('Invalid window audit row')
            row=decode(raw); stamp=integer(row['arrivalMs'])
            inside=start<=stamp<=end
            kind=row.get('kind'); data=row.get('data',{})
            if kind=='RAW_MARKET' and inside:
                if first is None: first=stamp
                else: largest=max(largest,stamp-last)
                last=stamp
            if kind=='RESEARCH_FEED_ERROR':
                if inside: errors+=1
                else: outside_errors+=1
            events=([{'kind':'GAP','data':data}] if kind=='RESEARCH_GAP'
                    else data.get('events',[]) if kind=='RESEARCH_FRAME' else [])
            if not inside:
                for event in events:
                    if event['kind']=='GAP': excluded[event['data'].get('reason','unknown')]+=1
    if first is not None: largest=max(largest,first-start,end-last)
    else: largest=max(0,end-start)
    return {'excludedGaps':excluded,'windowErrors':errors,'outsideErrors':outside_errors,
            'rawRecordsPresent':first is not None,'largestGapMs':largest}


def tape_bounds(path):
    stats = journal_stats(path)
    return stats['firstMs'], stats['lastMs']

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
        tape_health = journal_stats(path)
        first, last = tape_health['firstMs'], tape_health['lastMs']
        clob.append({'path': str(path), 'startMs': first, 'endMs': last,
                     'rawMarketRecords': tape_health['rawMarketRecords'],
                     'largestRawMarketGapMs': tape_health['largestRawMarketGapMs'],
                     'complete': report['recordingClosedCleanly'],
                     'gaps': report['gapReasons'], 'errors': report['errors'],
                     'format': report['frameAtomicity'],
                     'rawFrames': report['events'].get('RAW_MARKET', 0),
                     'books': report['normalizedEvents'].get('BOOK', 0)})
    clob.sort(key=lambda x: x['startMs'])
    common_start = max(cex['startedAtMs'], clob[0]['startMs'])
    common_end = min(cex['endedAtMs'], clob[-1]['endMs'])
    first_midnight = ((common_start + DAY_MS - 1) // DAY_MS) * DAY_MS
    window_end = min(common_end,first_midnight+days*DAY_MS)
    issues = list(cex['issues'])
    for i, tape in enumerate(clob):
        health=window_health(tape['path'],max(first_midnight,tape['startMs']),
                             min(window_end,tape['endMs']))
        scoped_gaps={k:max(0,v-health['excludedGaps'].get(k,0)) for k,v in tape['gaps'].items()}
        if not tape['complete']:
            issues.append('POLYMARKET_INCOMPLETE_TAPE')
        if (health['windowErrors'] or tape['errors'] and not health['outsideErrors']
                or any(scoped_gaps.values())):
            issues.append('POLYMARKET_SOURCE_GAPS_OR_ERRORS')
        if tape['format'] != 'recorded-frame-v1' or tape['rawFrames'] < 1 or tape['books'] < 1:
            issues.append('POLYMARKET_FRAME_DEPTH_EVIDENCE_MISSING')
        if tape['rawMarketRecords'] < 1:
            issues.append('POLYMARKET_NO_RAW_MARKET_RECORDS')
        elif health['largestGapMs'] > max_gap_ms:
            issues.append('POLYMARKET_SILENT_MARKET_GAP')
        if i:
            if tape['startMs'] < clob[i-1]['endMs']:
                issues.append('POLYMARKET_OVERLAPPING_RUNS')
            if min(tape['startMs'],window_end) - max(clob[i-1]['endMs'],first_midnight) > max_gap_ms:
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
            'largestClobRawMarketGapMs':max(
                (t['largestRawMarketGapMs'] for t in clob), default=None),
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
