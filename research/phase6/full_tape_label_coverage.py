"""Streaming coverage census, not an account replay or execution simulator.

Replay coordinates are original journal sequence + frame-event index. Unknown
observations remain missing; neither public prints nor zero credits fill gaps.
"""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re

from research.phase3.polybot_sdk.tapes import open_tape, stored_sha256

ROOT = Path('research/phase6/full-tape-coverage-freeze.json')
MAX_ROW_BYTES = 16 * 1024 * 1024
MAX_MARKETS = 10000
MAX_MISSING_BYTES = 256 * 1024 * 1024
FRAME_KINDS = {'BOOK', 'TRADE', 'TICK_SIZE', 'GAP'}
INPUT_KINDS = FRAME_KINDS | {'FRAME', 'META', 'GROUP_META', 'GROUP_SETTLEMENT',
                           'RESOLUTION', 'FEED_ERROR', 'MARKET_UNAVAILABLE', 'EXTERNAL_PROPOSAL'}


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('Nonnegative integer required')
    return value


def census(stream, labels, emit_missing, *, expected_sha, expected_rows):
    if (labels.get('experiment') != 'CONSERVED-MIXED-LAB0'
            or labels.get('logicalTapeSha256') != expected_sha
            or labels.get('expectedBindingCount') != len(labels['bindings'])):
        raise ValueError('Changed validated label manifest/source')
    bindings = {(b['seq'], b['eventIndex']): b for b in labels['bindings']}
    transactions = {b['transactionHash'] for b in bindings.values()}
    if len(bindings) != len(labels['bindings']) or len(transactions) != len(bindings):
        raise ValueError('Duplicate label coordinate/transaction')
    pair = set(labels['coverage']['pair'])
    if len(pair) != 2:
        raise ValueError('Binary scoped label pair required')
    seen = set(); markets = {}; token_conditions = {}
    rows = 0; last = -1; run = None; declared = False; ended = False
    pending = None; previous_frame = -1; first_ms = None
    kinds = Counter(); events = Counter(); counts = Counter(); sides = Counter()
    market_counts = {}; first_missing = {}; logical = hashlib.sha256()
    observation_digest = hashlib.sha256(); missing_digest = hashlib.sha256()
    missing_bytes = 0; normalized_trades = 0

    def event(kind, data, row, index):
        nonlocal normalized_trades, missing_bytes
        events[kind] += 1
        if kind != 'TRADE':
            return
        normalized_trades += 1
        token = data['token']; side = data['side']; source = _integer(data['sourceMs'])
        if not isinstance(token, str) or not token or side not in ('BUY', 'SELL'):
            raise ValueError('Invalid normalized trade identity')
        for name in ('price', 'size'):
            value = Decimal(str(data[name]))
            if not value.is_finite() or value <= 0 or name == 'price' and value >= 1:
                raise ValueError('Invalid normalized trade price/size')
        raw = data.get('tradeId')
        if not isinstance(raw, str) or not raw or len(raw) > MAX_ROW_BYTES:
            raise ValueError('Missing original trade identity')
        public_hash = hashlib.sha256(raw.encode()).hexdigest()
        sample = None
        try:
            sample = json.loads(raw)
        except json.JSONDecodeError:
            pass
        tx = sample.get('transaction_hash') if isinstance(sample, dict) else None
        if not isinstance(tx, str) or re.fullmatch('0x[0-9a-f]{64}', tx) is None:
            tx = None
        key = (row['seq'], index); bound = bindings.get(key)
        if bound is not None:
            if key in seen or any((bound['at'] != row['arrivalMs'], bound['sourceMs'] != source,
                    bound['token'] != token, bound['side'] != side,
                    bound['publicTradeIdSha256'] != public_hash, bound['transactionHash'] != tx,
                    Decimal(str(bound['price'])) != Decimal(str(data['price'])),
                    Decimal(str(bound['size'])) != Decimal(str(data['size'])))):
                raise ValueError('Changed original bound observation')
            seen.add(key); status = 'BOUND_CONSERVED_GROUP'
        elif tx in transactions:
            status = 'KNOWN_TRANSACTION_AGGREGATE_SUPPRESSED'
        elif token in pair:
            status = 'MISSING_SCOPED_PAIR_LABEL'
        elif token in token_conditions:
            status = 'OTHER_MARKET_UNBOUND_NO_AGGREGATE_FALLBACK'
        else:
            status = 'UNKNOWN_MARKET_UNBOUND'
        condition = token_conditions.get(token, 'UNKNOWN')
        counts[status] += 1; sides[side] += 1
        market_counts.setdefault(condition, Counter())[status] += 1
        identity = dict(seq=row['seq'], eventIndex=index, at=row['arrivalMs'], sourceMs=source,
                        token=token, condition=condition, side=side, price=data['price'], size=data['size'],
                        publicTradeIdSha256=public_hash, transactionHash=tx, coverage=status)
        encoded = (json.dumps(identity, sort_keys=True, separators=(',', ':')) + '\n').encode()
        observation_digest.update(encoded)
        if status not in ('BOUND_CONSERVED_GROUP', 'KNOWN_TRANSACTION_AGGREGATE_SUPPRESSED'):
            missing_bytes += len(encoded)
            if missing_bytes > MAX_MISSING_BYTES:
                raise ValueError('Missing-evidence cap exceeded; never truncate')
            missing_digest.update(encoded); emit_missing(encoded)
            first_missing.setdefault(status, identity)

    for line in stream:
        if not line.endswith(b'\n') or len(line) > MAX_ROW_BYTES:
            raise ValueError('Incomplete/oversized tape row')
        logical.update(line); row = json.loads(line); rows += 1
        at = _integer(row['arrivalMs']); kind = row['kind']; data = row['data']
        if (type(row.get('schema')) is not int or row['schema'] != 1
                or type(row.get('seq')) is not int or row['seq'] != rows or at < last or ended
                or not isinstance(row.get('runId'), str) or not row['runId']
                or run is not None and row['runId'] != run):
            raise ValueError('Invalid tape chronology/schema/run')
        last = at; run = row['runId']; kinds[kind] += 1
        if first_ms is None:
            first_ms = at
        if kind == 'DATASET_CONFIG':
            if declared or data.get('format') != 'normalized-public-v2' or data.get('strategyIndependent') is not True:
                raise ValueError('Expected one original strategy-independent framed dataset')
            declared = True
        elif kind == 'RAW_MARKET':
            frame = _integer(data['frameId'])
            if not declared or pending is not None or frame <= previous_frame:
                raise ValueError('Missing/duplicate/unordered raw frame boundary')
            pending = frame
        elif kind == 'RESEARCH_FRAME':
            if pending is None or _integer(data['frameId']) != pending or not isinstance(data['events'], list):
                raise ValueError('Normalized frame has no matching raw observation')
            if 'decodedMs' in data and _integer(data['decodedMs']) > at:
                raise ValueError('Invalid frame decoder clock')
            for index, item in enumerate(data['events']):
                if item['kind'] not in FRAME_KINDS:
                    raise ValueError('Unsupported frame event; never omit')
                event(item['kind'], item['data'], row, index)
            previous_frame = pending; pending = None
        elif kind.startswith('RESEARCH_'):
            inp = kind[9:]
            if inp not in INPUT_KINDS or inp in {'BOOK', 'TRADE', 'TICK_SIZE'}:
                raise ValueError('Unsupported/unframed research input; never omit')
            if inp == 'META':
                condition = data['condition']; a = data['first']; b = data['second']
                if not all(isinstance(v, str) and v for v in (condition, a, b)) or a == b:
                    raise ValueError('Invalid market identity')
                if condition in markets and markets[condition] != (a, b):
                    raise ValueError('Market pair identity changed')
                markets[condition] = (a, b)
                if len(markets) > MAX_MARKETS:
                    raise ValueError('Market bound exceeded; never truncate')
                for token in (a, b):
                    if token in token_conditions and token_conditions[token] != condition:
                        raise ValueError('Ambiguous token ownership')
                    token_conditions[token] = condition
            event(inp, data, row, 0)
        elif kind == 'RUN_END':
            if data.get('complete') is not True:
                raise ValueError('Incomplete RUN_END')
            ended = True
    if (not declared or not ended or pending is not None or rows != expected_rows
            or logical.hexdigest() != expected_sha or seen != set(bindings)):
        raise ValueError('Incomplete original tape/hash/frame/label consumption')
    missing = normalized_trades - len(seen) - counts['KNOWN_TRANSACTION_AGGREGATE_SUPPRESSED']
    return dict(schema=1, scope='FULL_ORIGINAL_TAPE_LABEL_COVERAGE_ONLY_NOT_ACCOUNT_REPLAY',
        logicalTapeSha256=logical.hexdigest(), sourceRows=rows, runId=run, startMs=first_ms, endMs=last,
        completeOriginalChronologyChecked=True, frameBoundariesChecked=True,
        marketCount=len(markets), journalKinds=dict(kinds), normalizedEvents=dict(events),
        normalizedTradeObservations=normalized_trades, sides=dict(sides), coverageCounts=dict(counts),
        consumedBindings=len(seen), missingObservationCount=missing,
        missingObservationBytes=missing_bytes, missingObservationsLogicalSha256=missing_digest.hexdigest(),
        allObservationIdentitiesSha256=observation_digest.hexdigest(), firstMissingByReason=first_missing,
        coverageByCondition={k:dict(v) for k,v in sorted(market_counts.items())},
        uncoveredObservationsTreatedAsZero=False, publicAggregateFallbackAllowed=False,
        observedTradeRoutesFullyLabeled=missing == 0, fullAccountReplayAuthorized=False,
        adapterScopeStillPartial=True, receiptRequests=0, modelFillsCreated=0, netPnlRecomputed=False,
        independentPaperQualificationAllowed=False, liveAllowed=False, decision='NO_GO')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); frozen = json.loads(ROOT.read_text())
    for path, sha in frozen['filesSha256'].items():
        if stored_sha256(path) != sha:
            raise ValueError('Frozen coverage dependency changed: ' + path)
    # Complete offline receipt/route validation, not a new RPC request.
    from research.phase6.mixed_replay_labels import export
    labels = export()
    encoded_labels = (json.dumps(labels, indent=2) + '\n').encode()
    if hashlib.sha256(encoded_labels).hexdigest() != frozen['labelsSha256']:
        raise ValueError('Changed revalidated labels')
    tapes = [*args.input_root.rglob('events.jsonl.gz'), *args.input_root.rglob('events.jsonl')]
    if len(tapes) != 1 or stored_sha256(tapes[0]) != frozen['storedTapeSha256']:
        raise ValueError('Require exactly one unchanged compressed original tape')
    args.output.mkdir(parents=True, exist_ok=False)
    partial = args.output / 'missing-observations.jsonl.gz.partial'
    with partial.open('xb') as target:
        with gzip.GzipFile(filename='', fileobj=target, mode='wb', mtime=0) as saved:
            with open_tape(tapes[0]) as stream:
                result = census(stream, labels, saved.write,
                    expected_sha=frozen['logicalTapeSha256'], expected_rows=frozen['sourceRows'])
    final = args.output / 'missing-observations.jsonl.gz'; partial.rename(final)
    result.update(labelsSha256=frozen['labelsSha256'], missingObservationsCompressedSha256=stored_sha256(final),
                  coverageFreezeSha256=stored_sha256(ROOT))
    (args.output / 'coverage.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('coverageByCondition', 'firstMissingByReason')}), flush=True)


if __name__ == '__main__':
    main()
