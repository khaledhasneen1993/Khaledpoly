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
    digest = hashlib.sha256()
    decimal = lambda x: Decimal(str(x))
    age = config['maxBookAgeMs']; metadata_age = config['metadataMaxAgeMs']
    def event(kind, data, at):
        nonlocal trades
        if kind == 'GAP':
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
                    token = data['token']; m = markets.get(tokens.get(token))
                    reason = 'NO_FRESH_ACTIVE_BINARY_MARKET'
                    if m and m['condition'] not in resolved and m['accepting'] and m['startMs'] <= at < m['endMs'] and 0 <= at-m['observedMs'] <= metadata_age:
                        a = books.get(token); b = books.get(m['second'] if token == m['first'] else m['first'])
                        reason = 'DEPTH_UNAVAILABLE'
                        if a and b and all(0 <= at-book['sourceMs'] <= age and book['bids'] and book['asks'] for book in (a,b)):
                            source = data['sourceMs']; reason = 'INVALID_OR_OLD_PRINT_SOURCE'
                            if 0 <= at-source <= age and source >= a['sourceMs']:
                                tick = decimal(m['tick']); quote = []; depth = []
                                for book in (a,b):
                                    bids = {decimal(x['price']): decimal(x['size']) for x in book['bids']}
                                    asks = {decimal(x['price']): decimal(x['size']) for x in book['asks']}
                                    price = min(max(bids)+improvement*tick, min(asks)-tick)
                                    quote.append(price//tick*tick); depth.append(bids[max(bids)])
                                quantity = min(decimal(config['orderShares']), min(depth)*Decimal('.1')).quantize(Decimal('.01'), rounding='ROUND_DOWN')
                                reason = 'NEW_ENTRY_MIN_SIZE'
                                if quantity >= decimal(m['minSize']):
                                    reason = 'QUOTE_NOT_AT_PRINT'
                                    if decimal(data['price']) == quote[0]:
                                        net = (1-sum(quote))*quantity-decimal(config['mergeCost'])
                                        reason = 'BELOW_BASE_EDGE_FLOOR'
                                        if net >= decimal(config['minimumEdge'])*quantity:
                                            reason = 'NECESSARY_CONDITIONS_ONLY'
                                            if len(examples) < 50:
                                                examples.append({'at': at, 'condition': m['condition'], 'token': token,
                                                                 'improvementTicks': improvement, 'printPrice': str(quote[0]),
                                                                 'printSize': str(data['size']), 'otherQuote': str(quote[1]),
                                                                 'netEdgeUpperBound': str(net/quantity)})
                reasons[improvement][reason] += 1
    for line in stream:
        digest.update(line); row = json.loads(line); count += 1
        if row.get('schema') != 1 or row.get('seq') != count or row['arrivalMs'] < last or clean:
            raise ValueError('Invalid or unclosed journal chronology')
        if run_id is None: run_id = row['runId']
        if row['runId'] != run_id: raise ValueError('Mixed journal runs')
        last = row['arrivalMs']; kind = row['kind']; data = row['data']
        if kind == 'RESEARCH_META':
            markets[data['condition']] = data
            for token in (data['first'], data['second']): tokens[token] = data['condition']
        elif kind == 'RESEARCH_FRAME':
            for item in data['events']: event(item['kind'], item['data'], last)
        elif kind in ('RESEARCH_GAP', 'RESEARCH_BOOK', 'RESEARCH_TRADE'):
            event(kind.removeprefix('RESEARCH_'), data, last)
        elif kind in ('RESEARCH_RESOLUTION', 'RESEARCH_MARKET_UNAVAILABLE'):
            resolved.add(data['condition'])
        elif kind == 'RESEARCH_FEED_ERROR': books.clear()
        elif kind == 'RUN_END':
            clean = data.get('complete') is True
            if not clean: raise ValueError('Incomplete RUN_END')
    if not clean: raise ValueError('Missing complete RUN_END')
    return {'scope': 'NORMALIZED_PRINT_NECESSARY_CONDITION_UPPER_BOUND', 'rows': count,
            'logicalTapeSha256': digest.hexdigest(), 'runId': run_id, 'recordingClosedCleanly': clean,
            'observedTrades': trades, 'oneClassificationPerPrintPerPolicy': True,
            'policyCounts': {str(k): dict(v) for k,v in reasons.items()}, 'examples': examples,
            'omittedConstraints': ['dynamic risk premiums', 'activation latency', 'queue depletion',
                                   'order placement before the print', 'available account budget', 'inventory risk'],
            'fillsInferred': False, 'pnlInferred': False, 'decision': 'NO_GO', 'liveAllowed': False}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--input-root', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); tapes = [*Path(a.input_root).rglob('events.jsonl.gz'), *Path(a.input_root).rglob('events.jsonl')]
    if len(tapes) != 1: raise ValueError('Expected one unambiguous journal')
    with open_tape(tapes[0]) as stream:
        result = census(stream, json.loads(Path('research/phase2/research-config.json').read_text()))
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(result, indent=2)); print(json.dumps({k:v for k,v in result.items() if k != 'examples'}), flush=True)


if __name__ == '__main__': main()
