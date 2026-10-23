"""Read-only continuity audit of FROZEN own fills; never an execution/PnL model.

Same-arrival GAP/invalid depth conservatively censors that arrival's observations,
regardless of event order. This is stricter than event-by-event Java telemetry;
it does not claim to rerun the strategy or reproduce its account.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape


HORIZONS = (1000, 5000, 30000)


class Coverage:
    def __init__(self, executions, pairs, max_age):
        if not executions or len(executions) > 100 or max_age <= 0:
            raise ValueError('Invalid bounded audit specification')
        self.pairs = {k: set(v) for k, v in pairs.items()}
        if any(len(v) != 2 for v in self.pairs.values()):
            raise ValueError('Binary metadata required')
        self.targets = set().union(*self.pairs.values())
        self.fills = []
        for index, fill in enumerate(executions):
            if (fill['token'] not in self.pairs[fill['condition']]
                    or not isinstance(fill['buy'], bool)
                    or fill['liquidity'] != 'MAKER'
                    or Decimal(str(fill['size'])) <= 0
                    or not 0 < Decimal(str(fill['price'])) < 1):
                raise ValueError('Unsupported frozen fill')
            self.fills.append(dict(fill, fillIndex=index))
        self.max_age = max_age
        self.books = {}
        self.pending, self.results = [], []
        self.inserted = set()
        self.metadata = set()
        self.last = -1

    def finish(self, pending, status, proof, **extra):
        self.results.append(dict(fillIndex=pending['fillIndex'], orderId=pending['orderId'],
            token=pending['token'], fillMs=pending['at'], horizonMs=pending['horizonMs'],
            status=status, proof=proof, **extra))

    def invalidate(self, tokens, reason, proof):
        keep = []
        for pending in self.pending:
            if not tokens or pending['token'] in tokens:
                self.finish(pending, reason, proof)
            else:
                keep.append(pending)
        self.pending = keep

    def scope(self, data):
        if not isinstance(data.get('tokens', []), list):
            raise ValueError('Invalid GAP scope array')
        tokens = set(data.get('tokens', []))
        if data.get('token') is not None:
            tokens.add(data['token'])
        if len(tokens) > 128 or any(not isinstance(t, str) or not t for t in tokens):
            raise ValueError('Invalid GAP scope')
        return tokens | set().union(*(v for v in self.pairs.values() if tokens & v))

    def arrival(self, at, events):
        if at <= self.last:
            raise ValueError('Arrival groups must be strictly increasing')
        self.last = at
        for kind, data, proof in events:
            if kind == 'META' and data.get('condition') in self.pairs:
                if ({data['first'], data['second']} != self.pairs[data['condition']]
                        or data['observedMs'] > at):
                    raise ValueError('Frozen pair metadata mismatch/future observation')
                self.metadata.add(data['condition'])
        stale = {token for token, book in self.books.items() if at-book['source'] > self.max_age}
        if stale:
            self.invalidate(stale, 'STALE_DEPTH', dict(at=at, lastSources={
                token:self.books[token]['source'] for token in sorted(stale)}))
            for token in stale:
                self.books.pop(token)
        # Process GAPs first at the same arrival. Never manufacture a clean sample
        # from ordering ambiguity at millisecond-resolution receive timestamps.
        uncertain = set()
        for kind, data, proof in events:
            if kind != 'GAP':
                continue
            scope = self.scope(data)
            affected = scope or self.targets
            uncertain |= affected
            self.invalidate(scope, 'DATA_GAP', proof)
            for token in affected:
                self.books.pop(token, None)
        observations = []
        for kind, data, proof in events:
            if kind != 'BOOK' or data.get('token') not in self.targets:
                continue
            token = data['token']; source = data.get('sourceMs', -1)
            bids = [Decimal(str(x['price'])) for x in data.get('bids', [])
                    if Decimal(str(x['size'])) > 0]
            asks = [Decimal(str(x['price'])) for x in data.get('asks', [])
                    if Decimal(str(x['size'])) > 0]
            prior = self.books.get(token)
            if (source < 0 or source > at or at-source > self.max_age
                    or prior and source < prior['source'] or not bids or not asks
                    or any(not p.is_finite() or not 0 < p < 1 for p in bids+asks)
                    or max(bids) >= min(asks)):
                uncertain.add(token)
                self.invalidate({token}, 'INVALID_BOOK', proof)
                self.books.pop(token, None)
                continue
            book = dict(source=source, mid=(max(bids)+min(asks))/2, proof=proof)
            self.books[token] = book
            observations.append((token, book))
        if uncertain:
            self.invalidate(uncertain, 'SAME_ARRIVAL_UNCERTAINTY', dict(at=at))
        for token, book in observations:
            if token in uncertain:
                continue
            keep = []
            for pending in self.pending:
                due = pending['at']+pending['horizonMs']
                if at > due+2000:
                    self.finish(pending, 'OBSERVATION_WINDOW_EXPIRED', dict(at=at))
                elif pending['token'] == token and at >= due and book['source'] >= due:
                    per_share = (book['mid']-Decimal(str(pending['price']))) * (1 if pending['buy'] else -1)
                    self.finish(pending, 'VALID', book['proof'], sourceMs=book['source'],
                        midPrice=str(book['mid']),
                        perShare=str(per_share), quantity=str(pending['size']),
                        markoutNotAccountPnl=str(per_share*Decimal(str(pending['size']))))
                else:
                    keep.append(pending)
            self.pending = keep
        for fill in self.fills:
            if fill['fillIndex'] in self.inserted or fill['at'] != at:
                continue
            if fill['condition'] not in self.metadata:
                raise ValueError('Fill precedes verified pair metadata')
            # All frozen fills are maker print-driven; no fill is inferred here.
            if not any(kind == 'TRADE' and data.get('token') in self.pairs[fill['condition']]
                       for kind, data, proof in events):
                raise ValueError('Frozen fill arrival lacks its recorded trade group')
            self.inserted.add(fill['fillIndex'])
            for horizon in HORIZONS:
                pending = dict(fill, horizonMs=horizon)
                if fill['token'] in uncertain:
                    self.finish(pending, 'FILL_ARRIVAL_UNCERTAINTY', dict(at=at))
                elif fill['token'] not in self.books:
                    self.finish(pending, 'FILL_DEPTH_UNAVAILABLE', dict(at=at))
                else:
                    self.pending.append(pending)

    def report(self):
        if len(self.inserted) != len(self.fills):
            raise ValueError('Frozen fill arrivals were not all observed')
        for pending in self.pending:
            self.finish(pending, 'RECORDING_ENDED_BEFORE_CLEAN_OBSERVATION', dict(at=self.last))
        self.pending = []
        counts = Counter(r['status'] for r in self.results)
        if len(self.results) != len(self.fills)*len(HORIZONS):
            raise ValueError('Horizon coverage is not conserved')
        return dict(scope='DEVELOPMENT_FROZEN_FILL_CONTINUITY_AUDIT_NOT_ACCOUNT_REPLAY',
            policy='CONSERVATIVE_SAME_ARRIVAL_GROUP_CENSORING', maxBookAgeMs=self.max_age,
            frozenExecutions=self.fills,
            frozenFills=len(self.fills), expectedHorizons=len(self.results), statusCounts=dict(counts),
            horizons=sorted(self.results, key=lambda r:(r['fillIndex'],r['horizonMs'])),
            fillsInferred=False, netPnlRecomputed=False, independentPaperQualificationAllowed=False,
            liveAllowed=False, decision='NO_GO')


def audit(stream, executions, pairs, max_age, expected_sha):
    coverage = Coverage(executions, pairs, max_age)
    digest = hashlib.sha256(); seq = 0; last = -1; run = None; ended = False
    group = []; group_at = None; declared = False; raw_frame = None; previous_frame = -1
    for raw in stream:
        if len(raw) > 16*1024*1024 or not raw.endswith(b'\n'):
            raise ValueError('Oversized or incomplete tape row')
        digest.update(raw); row = json.loads(raw); seq += 1
        at = row['arrivalMs']; kind = row['kind']; data = row['data']
        if (row['schema'] != 1 or row['seq'] != seq or at < last or at < 0 or ended
                or run is not None and row['runId'] != run):
            raise ValueError('Invalid tape chronology/schema/run')
        run = row['runId']; last = at
        if group_at is not None and at != group_at:
            coverage.arrival(group_at, group); group = []
        group_at = at
        if kind == 'DATASET_CONFIG':
            if declared or data.get('format') != 'normalized-public-v2':
                raise ValueError('Require one normalized-public-v2 declaration')
            declared = True
        if kind == 'RAW_MARKET':
            frame = data.get('frameId', -1)
            if raw_frame is not None or frame <= previous_frame:
                raise ValueError('Invalid raw frame boundary')
            raw_frame = frame
        if kind == 'RESEARCH_FRAME':
            if not declared or raw_frame is None or data.get('frameId') != raw_frame:
                raise ValueError('Unbound normalized frame')
            previous_frame = raw_frame; raw_frame = None
            events = data['events']
            if len(events) > 10000:
                raise ValueError('Oversized normalized frame')
            for index, event in enumerate(events):
                if event['kind'] not in ('BOOK', 'TRADE', 'GAP', 'TICK_SIZE'):
                    raise ValueError('Unsupported normalized frame event')
                d = event['data']
                if d.get('token') in coverage.targets or event['kind'] == 'GAP':
                    group.append((event['kind'], d, dict(seq=seq, eventIndex=index, at=at,
                        kind=event['kind'], data=d if event['kind']=='GAP' else {'token':d.get('token')})))
        elif kind.startswith('RESEARCH_'):
            event_kind = kind[9:]
            if event_kind == 'FEED_ERROR': event_kind = 'GAP'
            if event_kind in ('META', 'GAP', 'BOOK', 'TRADE'):
                group.append((event_kind, data, dict(seq=seq, at=at, kind=event_kind,
                    data=data if event_kind=='GAP' else {'token':data.get('token')})))
        if len(group) > 100000:
            raise ValueError('Unbounded arrival group')
        if kind == 'RUN_END':
            ended = data.get('complete') is True
            if not ended: raise ValueError('Incomplete recording')
    if not ended or not declared or raw_frame is not None or digest.hexdigest() != expected_sha:
        raise ValueError('Unclosed recording/frame or logical tape hash mismatch')
    if group_at is not None: coverage.arrival(group_at, group)
    return dict(coverage.report(), logicalTapeSha256=digest.hexdigest(), sourceRows=seq, runId=run)


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True)
    p.add_argument('--output',required=True);args=p.parse_args()
    frozen=json.loads(Path('research/phase6/markout-coverage-freeze.json').read_text())
    for name, sha in frozen['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:
            raise ValueError('Frozen continuity audit input/code changed: '+name)
    original=json.loads(Path(frozen['originalReport']).read_text())
    tapes=[*Path(args.input_root).rglob('events.jsonl.gz'),*Path(args.input_root).rglob('events.jsonl')]
    if len(tapes)!=1: raise ValueError('Require one complete unambiguous tape')
    with open_tape(tapes[0]) as stream:
        result=audit(stream, original['executions'], frozen['pairs'],
            original['configuration']['maxBookAgeMs'], frozen['logicalTapeSha256'])
    result.update(originalReportSha256=frozen['filesSha256'][frozen['originalReport']],
        originalAccountNetPnl=original['netRealizedPnl'], originalAccountCash=original['cash'],
        caveat='Existing partial offline settlement labels remain unqualified; this audit changes no account or strategy decisions.')
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x') as output: output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='horizons'}),flush=True)


if __name__=='__main__': main()
