"""Necessary-condition census of recorded prints, NEVER an execution or profit simulator.

Ignores dynamic risk premiums, activation and queue depletion. Passing this upper-bound
screen cannot establish a feasible fill. Books/prices come only from earlier tape rows.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape


def census(stream, config):
    markets = {}; tokens = {}; books = {}; resolved = set(); reasons = {0: Counter(), 1: Counter()}
    examples = []; count = trades = 0; last = -1; clean = False; run_id = None
    complement_reasons = {0: Counter(), 1: Counter()}; fingerprints = {}; raw_fields = Counter()
    raw_trade_samples = []; raw_trade_count = 0
    digest = hashlib.sha256()
    decimal = lambda x: Decimal(str(x))
    age = config['maxBookAgeMs']; metadata_age = config['metadataMaxAgeMs']
    def classify(data, at, improvement, token, price, route):
        m = markets.get(tokens.get(token))
        if not (m and m['condition'] not in resolved and m['accepting'] and m['startMs'] <= at < m['endMs']
                and 0 <= at-m['observedMs'] <= metadata_age): return 'NO_FRESH_ACTIVE_BINARY_MARKET'
        if route == 'COMPLEMENT_BUY_CANDIDATE' and m.get('negativeRisk', False): return 'UNVERIFIED_NEGATIVE_RISK_ROUTE'
        a = books.get(token); b = books.get(m['second'] if token == m['first'] else m['first'])
        if not (a and b and all(0 <= at-book['sourceMs'] <= age and book['bids'] and book['asks'] for book in (a,b))):
            return 'DEPTH_UNAVAILABLE'
        source = data['sourceMs']
        minimum_source = max(a['sourceMs'], b['sourceMs']) if route == 'COMPLEMENT_BUY_CANDIDATE' else a['sourceMs']
        if not (0 <= at-source <= age and source >= minimum_source): return 'INVALID_OR_OLD_PRINT_SOURCE'
        tick = decimal(m['tick']); quote = []; depth = []
        for book in (a,b):
            bids = {decimal(x['price']): decimal(x['size']) for x in book['bids']}
            asks = {decimal(x['price']): decimal(x['size']) for x in book['asks']}
            proposed = min(max(bids)+improvement*tick, min(asks)-tick)
            quote.append(proposed//tick*tick); depth.append(bids[max(bids)])
        quantity = min(decimal(config['orderShares']), min(depth)*Decimal('.1')).quantize(Decimal('.01'), rounding='ROUND_DOWN')
        if quantity < decimal(m['minSize']): return 'NEW_ENTRY_MIN_SIZE'
        if price != quote[0]: return 'QUOTE_NOT_AT_PRINT'
        net = (1-sum(quote))*quantity-decimal(config['mergeCost'])
        if net < decimal(config['minimumEdge'])*quantity: return 'BELOW_BASE_EDGE_FLOOR'
        identity = (improvement, m['condition'], token, source, price.normalize(), decimal(data['size']).normalize())
        if len(fingerprints) >= 100000 and identity not in fingerprints: raise ValueError('Rotate bounded census dataset')
        fingerprints.setdefault(identity, set()).add(route)
        if len(examples) < 2000:
            raw_identity = data.get('tradeId','')
            transaction = None
            if isinstance(raw_identity,str) and raw_identity.startswith('{') and len(raw_identity)<=65536:
                recorded_identity=json.loads(raw_identity)
                candidate_hash=recorded_identity.get('transaction_hash')
                if isinstance(candidate_hash,str) and len(candidate_hash)==66 and candidate_hash.startswith('0x'):
                    transaction=candidate_hash
            examples.append({'at': at, 'condition': m['condition'], 'token': token, 'route': route,
                             'firstToken':m['first'],'secondToken':m['second'],'sourceMs':source,
                             'transactionHash':transaction,'tradeIdSha256':hashlib.sha256(raw_identity.encode()).hexdigest(),
                             'reportedToken': data['token'], 'reportedSide': data['side'], 'reportedPrice': str(data['price']),
                             'improvementTicks': improvement, 'printPrice': str(price), 'printSize': str(data['size']),
                             'otherQuote': str(quote[1]), 'netEdgeUpperBound': str(net/quantity)})
        return 'NECESSARY_CONDITIONS_ONLY'

    def event(kind, data, at):
        nonlocal trades
        if kind == 'TICK_SIZE':
            market = markets.get(tokens.get(data['token']))
            if market and 0 <= at-data['sourceMs'] <= age:
                market['tick'] = str(max(decimal(market['tick']), decimal(data['tick'])))
        elif kind == 'GAP':
            scope = set(data.get('tokens', []))
            if data.get('token'): scope.add(data['token'])
            if not scope: books.clear()
            else:
                for token in list(scope):
                    market = markets.get(tokens.get(token))
                    if market: scope.update((market['first'], market['second']))
                for token in scope: books.pop(token, None)
        elif kind == 'BOOK':
            token = data['token']; source = data['sourceMs']; prior = books.get(token)
            if source > at or at-source > age or prior and source < prior['sourceMs']:
                books.pop(token, None)
            else: books[token] = data
        elif kind == 'TRADE':
            trades += 1
            for improvement in (0, 1):
                reason = 'WRONG_AGGRESSOR'
                if data['side'] == 'SELL':
                    reason = classify(data, at, improvement, data['token'], decimal(data['price']), 'DIRECT_SELL')
                reasons[improvement][reason] += 1
                if data['side'] == 'BUY':
                    m = markets.get(tokens.get(data['token']))
                    complement_reason = 'UNKNOWN_BINARY_COMPLEMENT'
                    if m:
                        other = m['second'] if data['token'] == m['first'] else m['first']
                        complement_reason = classify(data, at, improvement, other, 1-decimal(data['price']), 'COMPLEMENT_BUY_CANDIDATE')
                    complement_reasons[improvement][complement_reason] += 1
    for line in stream:
        digest.update(line); row = json.loads(line); count += 1
        if row.get('schema') != 1 or row.get('seq') != count or row['arrivalMs'] < last or clean:
            raise ValueError('Invalid or unclosed journal chronology')
        if run_id is None: run_id = row['runId']
        if row['runId'] != run_id: raise ValueError('Mixed journal runs')
        last = row['arrivalMs']; kind = row['kind']; data = row['data']
        if kind == 'RAW_MARKET' and 'last_trade_price' in data.get('text', ''):
            value = json.loads(data['text']); nodes = value if isinstance(value, list) else [value]
            for node in nodes:
                if node.get('event_type') != 'last_trade_price': continue
                raw_trade_count += 1; raw_fields.update(key for key,value in node.items() if value is not None)
                if len(raw_trade_samples) < 5:
                    raw_trade_samples.append({key:node[key] for key in ('asset_id','market','side','price','size','timestamp','transaction_hash','transactionHash') if key in node})
        elif kind == 'RESEARCH_META':
            markets[data['condition']] = data
            for token in (data['first'], data['second']): tokens[token] = data['condition']
        elif kind == 'RESEARCH_FRAME':
            for item in data['events']: event(item['kind'], item['data'], last)
        elif kind in ('RESEARCH_GAP', 'RESEARCH_BOOK', 'RESEARCH_TRADE', 'RESEARCH_TICK_SIZE'):
            event(kind.removeprefix('RESEARCH_'), data, last)
        elif kind == 'RESEARCH_RESOLUTION':
            resolved.add(data['condition_id'])
        elif kind == 'RESEARCH_MARKET_UNAVAILABLE':
            market = markets.get(data['condition'])
            if market: market['accepting'] = False
        elif kind == 'RESEARCH_FEED_ERROR': books.clear()
        elif kind == 'RUN_END':
            clean = data.get('complete') is True
            if not clean: raise ValueError('Incomplete RUN_END')
    if not clean: raise ValueError('Missing complete RUN_END')
    return {'scope': 'NORMALIZED_PRINT_NECESSARY_CONDITION_UPPER_BOUND', 'rows': count,
            'logicalTapeSha256': digest.hexdigest(), 'runId': run_id, 'recordingClosedCleanly': clean,
            'observedTrades': trades, 'oneClassificationPerPrintPerPolicy': True,
            'policyCounts': {str(k): dict(v) for k,v in reasons.items()}, 'examples': examples,
            'examplesLimit':2000,'examplesTruncated':sum(v.get('NECESSARY_CONDITIONS_ONLY',0) for v in (*reasons.values(),*complement_reasons.values()))>len(examples),
            'complementBuyCandidateCounts': {str(k):dict(v) for k,v in complement_reasons.items()},
            'routeFingerprintOverlaps': {str(k):sum(identity[0] == k and len(routes) > 1 for identity,routes in fingerprints.items()) for k in (0,1)},
            'routesMayDescribeSameExecution': True, 'complementPrintIsNotProofOfMint': True,
            'rawLastTradeCount': raw_trade_count, 'rawLastTradeFieldPresence': dict(raw_fields), 'rawLastTradeSamples': raw_trade_samples,
            'omittedConstraints': ['dynamic risk premiums', 'activation latency', 'queue depletion',
                                   'order placement before the print', 'available account budget', 'inventory risk'],
            'fillsInferred': False, 'pnlInferred': False, 'decision': 'NO_GO', 'liveAllowed': False}


def validate_reference(result, logical_sha=None, direct_zero=None, direct_one=None):
    if logical_sha is not None and result['logicalTapeSha256'] != logical_sha:
        raise ValueError('Logical tape hash differs from prior census')
    for policy, expected in (('0',direct_zero), ('1',direct_one)):
        if expected is not None and result['policyCounts'][policy].get('NECESSARY_CONDITIONS_ONLY',0) != expected:
            raise ValueError('Direct-route reference counts changed')


def main():
    p = argparse.ArgumentParser(); p.add_argument('--input-root', required=True); p.add_argument('--output', required=True)
    p.add_argument('--expected-logical-sha256'); p.add_argument('--expected-direct-zero',type=int); p.add_argument('--expected-direct-one',type=int)
    a = p.parse_args(); tapes = [*Path(a.input_root).rglob('events.jsonl.gz'), *Path(a.input_root).rglob('events.jsonl')]
    if len(tapes) != 1: raise ValueError('Expected one unambiguous journal')
    with open_tape(tapes[0]) as stream:
        result = census(stream, json.loads(Path('research/phase2/research-config.json').read_text()))
    validate_reference(result, a.expected_logical_sha256, a.expected_direct_zero, a.expected_direct_one)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(result, indent=2)); print(json.dumps({k:v for k,v in result.items() if k != 'examples'}), flush=True)


if __name__ == '__main__': main()
