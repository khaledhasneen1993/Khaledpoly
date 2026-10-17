"""Bounded read-only source accessibility evidence, not strategy qualification."""
import argparse
import hashlib
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from research.phase3.polybot_sdk.client import NoRedirect
from research.phase3.polybot_sdk.collector import PublicCollector
from research.phase3.polybot_sdk.model import decode, dumps
from research.phase3.polybot_sdk.runtime import private_write

GAMMA = 'https://gamma-api.polymarket.com'
CLOB = 'https://clob.polymarket.com'
UA = {'User-Agent': 'khaledpoly-public-readonly-probe/1'}


def _http(url):
    opener = build_opener(NoRedirect())
    with opener.open(Request(url, headers=UA, method='GET'), timeout=6) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Source payload exceeded 2 MiB')
    return decode(raw), hashlib.sha256(raw).hexdigest()


def _error(exc):
    if isinstance(exc, HTTPError):
        return {'status': 'BLOCKED_OR_HTTP_ERROR', 'httpStatus': exc.code}
    if isinstance(exc, (TimeoutError, URLError, OSError)):
        return {'status': 'UNREACHABLE', 'errorType': type(exc).__name__}
    return {'status': 'INVALID_RESPONSE', 'errorType': type(exc).__name__}


def public_source_probe():
    result = {'schema': 1, 'scope': 'ONE_TIME_PUBLIC_SOURCE_ACCESS_NOT_COVERAGE',
              'observedAtMs': int(time.time() * 1000), 'sources': {},
              'decision': 'NO_GO', 'liveAllowed': False,
              'continuousRecording': False, 'venueFillEvidence': False}
    for venue in ('binance-spot', 'bybit-spot'):
        collector = PublicCollector(venue)
        try:
            status, rows = collector.poll()
            result['sources'][venue] = {
                'status': status['status'], 'observedTradeRows': len(rows),
                'httpStatus': status.get('httpStatus'),
                'sourceAccessBlocked': status.get('sourceAccessBlocked', False),
                'coverage': 'ONE_REST_POLL_NOT_COMPLETE_TAPE'}
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
            result['sources'][venue] = _error(exc)
    try:
        info, digest = _http(CLOB + '/time')
        if isinstance(info, bool) or not (
                isinstance(info, (int, str)) and re.fullmatch(r'\d{9,15}', str(info))):
            raise ValueError('Unrecognized public CLOB time schema')
        result['sources']['polymarket-clob-time'] = {
            'status': 'AVAILABLE', 'payloadSha256': digest}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
        result['sources']['polymarket-clob-time'] = _error(exc)

    for category in ('politics', 'sports'):
        key = 'gamma-' + category
        try:
            tag, tag_hash = _http(GAMMA + '/tags/slug/' + category)
            if (not isinstance(tag, dict) or tag.get('slug') != category
                    or not str(tag.get('id', '')).isdigit()):
                raise ValueError('Invalid category tag identity')
            page, page_hash = _http(GAMMA + '/events/keyset?closed=false&limit=3&tag_id=' + str(tag['id']))
            if (not isinstance(page, dict) or not isinstance(page.get('events'), list)
                    or len(page['events']) > 3):
                raise ValueError('Invalid category event page')
            result['sources'][key] = {
                'status': 'AVAILABLE', 'tagSha256': tag_hash,
                'pageSha256': page_hash, 'eventCount': len(page['events']),
                'nextPageAvailable': bool(page.get('next_cursor')),
                'coverage': 'ONE_BOUNDED_PAGE_NOT_COMPLETE_UNIVERSE'}
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
            result['sources'][key] = _error(exc)
    result['reachableSources'] = sum(
        row['status'] in ('AVAILABLE', 'SAMPLED_PUBLIC_TRADES')
        for row in result['sources'].values())
    result['allSourcesReachable'] = result['reachableSources'] == len(result['sources'])
    return result


def main():
    parser = argparse.ArgumentParser(description='One-shot PUBLIC source audit, read-only')
    parser.add_argument('--output', required=True, help='New JSON path; never overwrite')
    args = parser.parse_args()
    result = public_source_probe()
    private_write(args.output, result)
    print(dumps(result))


if __name__ == '__main__':
    main()
