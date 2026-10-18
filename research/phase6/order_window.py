"""Selected original diagnostic rows; not a complete replay tape or a fill model."""
import argparse
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape


def related(kind, data, tokens, condition):
    if kind == 'RAW_MARKET':
        text = data.get('text', '')
        if 'last_trade_price' not in text or not any(token in text for token in tokens): return False
        value = json.loads(text)
        nodes = value if isinstance(value,list) else [value]
        return any(n.get('event_type') == 'last_trade_price' and n.get('asset_id') in tokens for n in nodes)
    if kind == 'RESEARCH_FRAME':
        return any(related('RESEARCH_'+item['kind'], item['data'], tokens, condition)
                   for item in data['events'])
    if kind in ('RESEARCH_GAP', 'RESEARCH_FEED_ERROR'):
        scope = set(data.get('tokens', []))
        if data.get('token'): scope.add(data['token'])
        return not scope or bool(scope & tokens)
    return (data.get('token') in tokens or data.get('condition') == condition
            or data.get('condition_id') == condition)


def extract(stream, specifications, expected_sha, limit=6000):
    digest = hashlib.sha256(); count = 0; last = -1; run_id = None; clean = False
    windows = [dict(spec=spec, rows=[], precedingMetadata=None, retainedBytes=0) for spec in specifications]
    if not windows or len(windows) > 4: raise ValueError('Require one to four fixed windows')
    for window in windows:
        spec = window['spec']
        if not 0 < spec['endMs']-spec['startMs'] <= 30000 or len(set(spec['tokens'])) != 2:
            raise ValueError('Invalid bounded binary window')
    for line in stream:
        digest.update(line); row = json.loads(line); count += 1
        if row.get('schema') != 1 or row.get('seq') != count or row['arrivalMs'] < last or clean:
            raise ValueError('Invalid journal chronology')
        if run_id is None: run_id = row['runId']
        if row['runId'] != run_id: raise ValueError('Mixed journal runs')
        last = row['arrivalMs']; kind = row['kind']; data = row['data']
        for window in windows:
            spec = window['spec']; tokens = set(spec['tokens'])
            if last < spec['startMs']:
                if kind == 'RESEARCH_META' and data.get('condition') == spec['condition']:
                    window['precedingMetadata'] = row
                continue
            if last > spec['endMs'] or not related(kind, data, tokens, spec['condition']): continue
            if len(window['rows']) >= limit or window['retainedBytes']+len(line) > 64000000:
                raise ValueError('Window evidence exceeds bound; rows='+str(len(window['rows']))+
                                 ' bytes='+str(window['retainedBytes'])+'; never silently truncate')
            window['rows'].append(row); window['retainedBytes'] += len(line)
        if kind == 'RUN_END':
            clean = data.get('complete') is True
            if not clean: raise ValueError('Incomplete recording')
    if not clean or digest.hexdigest() != expected_sha:
        raise ValueError('Incomplete recording or logical source hash mismatch')
    if any(not w['rows'] for w in windows): raise ValueError('Empty diagnostic window')
    return {'scope':'BOUNDED_ORIGINAL_ORDER_WINDOWS_NOT_REPLAY', 'logicalTapeSha256':digest.hexdigest(),
        'sourceRows':count, 'runId':run_id, 'recordingClosedCleanly':True, 'windows':windows,
        'rowsRetainOriginalSeqAndFrames':True, 'sourceBeforeWindowNotFullyReconstructed':True,
        'rawMarketSelection':'TARGET_LAST_TRADE_MESSAGES_ONLY; normalized books/frames retained unchanged',
        'fillsInferred':False, 'pnlInferred':False, 'decision':'NO_GO', 'liveAllowed':False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--input-root', required=True)
    parser.add_argument('--spec', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); spec = json.loads(Path(args.spec).read_text())
    tapes = [*Path(args.input_root).rglob('events.jsonl.gz'), *Path(args.input_root).rglob('events.jsonl')]
    if len(tapes) != 1: raise ValueError('Require one source tape')
    with open_tape(tapes[0]) as stream:
        result = extract(stream, spec['windows'], spec['logicalTapeSha256'])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open('x') as target: target.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'logicalTapeSha256':result['logicalTapeSha256'],
                      'retainedRows':[len(w['rows']) for w in result['windows']]}))


if __name__ == '__main__': main()
