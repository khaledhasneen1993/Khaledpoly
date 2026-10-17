"""Read-only category discovery, preserving protocol IDs without assuming an executable adapter."""
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from .client import NoRedirect
from .features import fingerprint
from .model import decode


class UniverseDiscovery:
    def __init__(self):
        self._opener = build_opener(NoRedirect())

    def _get(self, path):
        with self._opener.open(Request('https://gamma-api.polymarket.com' + path,
                               headers={'User-Agent': 'khaledpoly-paper-research/0.2'}, method='GET'), timeout=5) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('Discovery response exceeds bound')
        return decode(raw)

    def discover(self, category, limit=20):
        if category not in ('politics', 'sports') or not 1 <= limit <= 100:
            raise ValueError('Unsupported discovery category or limit')
        tag = self._get('/tags/slug/' + category)
        if tag.get('slug') != category or not str(tag.get('id', '')).isdigit():
            raise ValueError('Discovery tag identity mismatch')
        page = self._get('/markets/keyset?' + urlencode({'tag_id': tag['id'], 'closed': 'false', 'limit': limit}))
        if not isinstance(page.get('markets'), list) or len(page['markets']) > limit:
            raise ValueError('Invalid discovery page')
        markets, seen = [], set()
        for row in page['markets']:
            condition = row.get('conditionId')
            if not isinstance(condition, str) or not re.fullmatch('0x[0-9a-fA-F]{64}', condition) or condition in seen:
                raise ValueError('Unknown/duplicate discovered condition identity')
            seen.add(condition)
            markets.append({'condition': condition, 'version': row.get('version'), 'slug': row.get('slug'),
                            'clobTokenIds': row.get('clobTokenIds'), 'positionIds': row.get('positionIds'),
                            'rawMetadata': row, 'executionAdapterVerified': False})
        return {'category': category, 'observedMs': int(time.time() * 1000), 'tagEvidence': tag,
                'pageSha256': fingerprint(page), 'markets': markets, 'partialUniverse': bool(page.get('next_cursor')),
                'nextCursor': page.get('next_cursor'), 'executionEnabled': False, 'liveAllowed': False}
