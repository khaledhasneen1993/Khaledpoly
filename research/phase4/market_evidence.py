"""Bounded PUBLIC Polymarket event, binary identity, and book evidence.

Research-only. A sampled open event never proves a complete negative-risk
universe, official resolution, order execution, fees, or queue position.
"""
import argparse
from decimal import Decimal
import re
import time
from urllib.parse import urlencode

from research.phase3.polybot_sdk.model import decode, integer, number, dumps
from research.phase3.polybot_sdk.features import fingerprint
from research.phase3.polybot_sdk.runtime import private_write
from research.phase4.probe import GAMMA, CLOB, _http, _error

CONDITION = re.compile(r'0x[0-9a-fA-F]{64}\Z')
NUMBER_ID = re.compile(r'[0-9]{1,100}\Z')
CATEGORIES = ('politics', 'sports')


def _positive_id(value):
    return isinstance(value, str) and bool(NUMBER_ID.fullmatch(value)) and int(value) > 0


def _identity(market):
    """Validate V1/V2 IDs strictly; do not interchange position and token IDs."""
    if not isinstance(market, dict) or not _positive_id(market.get('id')):
        raise ValueError('Invalid market identifier')
    condition = market.get('conditionId')
    if not isinstance(condition, str) or not CONDITION.fullmatch(condition):
        raise ValueError('Invalid condition ID')
    protocol = market.get('version')
    if protocol not in ('v1', 'v2'):
        raise ValueError('Unknown market protocol version')
    field = 'clobTokenIds' if protocol == 'v1' else 'positionIds'
    values = market.get(field)
    if protocol == 'v1' and isinstance(values, str):
        values = decode(values)
    if (not isinstance(values, list) or len(values) != 2
            or any(not _positive_id(v) for v in values)
            or values[0] == values[1]):
        raise ValueError('Missing/ambiguous binary outcome IDs')
    forbidden = 'positionIds' if protocol == 'v1' else 'clobTokenIds'
    if market.get(forbidden) not in (None, ''):
        raise ValueError('Conflicting protocol ID families')
    return {'marketId': market['id'], 'condition': condition.lower(),
            'protocol': protocol, 'outcomeKind': 'clob-token' if protocol == 'v1' else 'position',
            'outcomeIds': values, 'binaryIdVerified': True}


def validate_event(event, expected_id):
    if (not isinstance(event, dict) or not _positive_id(event.get('id'))
            or event['id'] != expected_id or not isinstance(event.get('markets'), list)):
        raise ValueError('Invalid event identity or markets schema')
    # Very large sports events are common. Inspect bounded members; report
    # truncation explicitly rather than discarding the entire event or
    # silently pretending its full negative-risk universe was checked.
    maximum = 64
    seen_ids, seen_conditions, seen_outcomes = set(), set(), set()
    records, failures = [], []
    for i, row in enumerate(event['markets'][:maximum]):
        try:
            record = _identity(row)
            if (record['marketId'] in seen_ids or record['condition'] in seen_conditions
                    or any(v in seen_outcomes for v in record['outcomeIds'])):
                raise ValueError('Duplicate market/condition/outcome')
            seen_ids.add(record['marketId'])
            seen_conditions.add(record['condition'])
            seen_outcomes.update(record['outcomeIds'])
            records.append(record)
        except (ValueError, KeyError, TypeError) as exc:
            failures.append({'index': i, 'reason': str(exc)})
    # Never infer full negative-risk membership or terminal payouts from an event page.
    return {'eventId': expected_id, 'totalMarketRows': len(event['markets']),
            'inspectedMarketRows': min(len(event['markets']), maximum),
            'uninspectedMarketRows': max(0, len(event['markets']) - maximum),
            'marketListTruncated': len(event['markets']) > maximum,
            'verifiedBinaryMarkets': records, 'invalidMarketRows': failures,
            'multiMarketEvent': len(event['markets']) > 1,
            'negativeRiskFlagReported': event.get('negRisk') is True,
            'negativeRiskUniverseComplete': False,
            'terminalSettlementVerified': False}


def validate_book(book, expected_id):
    if not isinstance(book, dict):
        raise ValueError('Invalid book body')
    actual = book.get('asset_id')
    # Without venue-returned identity this is a sample, not a verified book.
    identity = actual is not None and str(actual) == expected_id
    if actual is not None and not identity:
        raise ValueError('Book asset ID mismatch')
    counts, truncated = {}, False
    for side in ('bids', 'asks'):
        rows = book.get(side)
        if not isinstance(rows, list):
            raise ValueError('Book has no bounded depth sides')
        if len(rows) > 200:
            truncated = True
        seen = set()
        for row in rows[:200]:
            if not isinstance(row, dict):
                raise ValueError('Invalid book price/size level')
            price, qty = number(row.get('price')), number(row.get('size'))
            if not Decimal(0) < price < Decimal(1) or qty <= 0 or price in seen:
                raise ValueError('Invalid duplicate or nonpositive book level')
            seen.add(price)
        counts[side] = min(len(rows), 200)
    return {'sourceIdentityVerified': identity, 'levels': counts,
            'depthTruncated': truncated,
            'venueFillEvidence': False, 'queueRankKnown': False}


def collect_event_evidence(category, limit=2, max_books=2):
    if category not in CATEGORIES or type(limit) is not int or not 1 <= limit <= 5 or type(max_books) is not int or not 0 <= max_books <= 8:
        raise ValueError('Invalid bounded category observation')
    evidence = {'schema': 1, 'scope': 'ONE_SHOT_POLYMARKET_CATEGORY_EVIDENCE',
                'category': category, 'observedAtMs': int(time.time()*1000),
                'events': [], 'errors': [], 'partialUniverse': True,
                'booksAttempted': 0, 'marketInfoAttempted': 0,
                'completeOrderBookHistory': False,
                'negativeRiskUniverseComplete': False, 'terminalSettlementVerified': False,
                'qualifiedFeeCurve': False, 'venueFillEvidence': False,
                'decision': 'NO_GO', 'liveAllowed': False}
    try:
        tag, tag_hash = _http(GAMMA+'/tags/slug/'+category)
        if not isinstance(tag, dict) or tag.get('slug') != category or not str(tag.get('id', '')).isdigit():
            raise ValueError('Invalid category tag identity')
        evidence['tagSha256'] = tag_hash
        page, page_hash = _http(GAMMA+'/events/keyset?'+urlencode({'tag_id':tag['id'],'closed':'false','limit':limit}))
        if not isinstance(page, dict) or not isinstance(page.get('events'), list) or len(page['events']) > limit:
            raise ValueError('Invalid bounded event page')
        evidence['pageSha256'] = page_hash
        evidence['hasAdditionalPage'] = bool(page.get('next_cursor'))
        evidence['pageEvents'] = len(page['events'])
    except (ValueError, KeyError, TypeError, OSError) as exc:
        evidence['errors'].append({'stage':'discovery', **_error(exc)})
        return evidence

    attempted = 0
    seen_events = set()
    for entry in page['events']:
        event_id = entry.get('id') if isinstance(entry, dict) else None
        if not _positive_id(event_id) or event_id in seen_events:
            evidence['errors'].append({'stage':'event_page', 'status':'INVALID_ID_OR_DUPLICATE'})
            continue
        seen_events.add(event_id)
        try:
            payload, digest = _http(GAMMA+'/events/'+event_id)
            record = validate_event(payload, event_id)
            record['payloadSha256'] = digest
            record['receivedMs'] = int(time.time()*1000)
            for market in record['verifiedBinaryMarkets']:
                if attempted >= max_books:
                    break
                attempted += 1
                evidence['marketInfoAttempted'] += 1
                try:
                    info, info_sha = _http(CLOB+'/clob-markets/'+market['condition'])
                    if not isinstance(info, dict):
                        raise ValueError('Invalid venue CLOB market-info')
                    market['marketInfo'] = {'status':'SAMPLED_UNQUALIFIED_FEE_CURVE',
                        'payloadSha256':info_sha, 'venueFeesVerified':False}
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    market['marketInfo'] = _error(exc)
                # A V2 position identifier is NOT interchangeable with a V1
                # CLOB token; do not assume a supported /book route for V2.
                if market['protocol'] != 'v1':
                    market['books'] = {'status':'UNVERIFIED_V2_BOOK_ADAPTER',
                                       'venueFillEvidence':False}
                    continue
                evidence['booksAttempted'] += 1
                try:
                    raw, sha = _http(CLOB+'/book?'+urlencode({'token_id':market['outcomeIds'][0]}))
                    parsed = validate_book(raw, market['outcomeIds'][0])
                    market['books'] = {**parsed, 'payloadSha256':sha,
                                       'status':'SAMPLED_NOT_CONTINUOUS'}
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    market['books'] = _error(exc)
                    if market['books'].get('httpStatus') == 404:
                        market['books']['status'] = 'BOOK_NOT_AVAILABLE_404'
                    elif isinstance(exc, (ValueError, KeyError, TypeError)):
                        market['books']['reason'] = str(exc)[:180]
            evidence['events'].append(record)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            evidence['errors'].append({'stage':'event_detail', 'eventId':event_id,
                                       'reason':str(exc)[:180] if isinstance(exc,(ValueError, KeyError, TypeError)) else None,
                                       **_error(exc)})
    evidence['verifiedMarkets'] = sum(len(e['verifiedBinaryMarkets']) for e in evidence['events'])
    evidence['invalidMarkets'] = sum(len(e['invalidMarketRows']) for e in evidence['events'])
    evidence['observedEvents'] = len(evidence['events'])
    return evidence


def main():
    parser = argparse.ArgumentParser(description='Bounded Polymarket metadata/book evidence; PAPER only')
    parser.add_argument('--category', choices=CATEGORIES, required=True)
    parser.add_argument('--limit', type=int, default=2)
    parser.add_argument('--max-books', type=int, default=2)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = collect_event_evidence(args.category, args.limit, args.max_books)
    private_write(args.output, result)
    print(dumps(result))


if __name__ == '__main__':
    main()
