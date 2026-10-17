"""Authenticated GET-only client. There is intentionally no order submission method."""
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
from .model import decode, validate


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Research redirects are forbidden')


class PaperClient:
    def __init__(self, origin, token, timeout=5):
        u = urlsplit(origin)
        if (u.scheme not in ('http', 'https') or not u.hostname or u.username is not None
                or u.password is not None or u.query or u.fragment or u.path not in ('', '/')
                or (u.scheme == 'http' and u.hostname not in ('127.0.0.1', 'localhost', '::1'))):
            raise ValueError('Use an HTTPS origin, or local HTTP, without credentials or path')
        if (not isinstance(token, str) or len(token) < 24 or not token.strip()
                or '\r' in token or '\n' in token):
            raise ValueError('Invalid executor token')
        if not 0 < timeout <= 30:
            raise ValueError('Invalid timeout')
        self._url, self._token, self._timeout = origin.rstrip('/') + '/api/research/v1/snapshot', token, timeout
        self._opener = build_opener(NoRedirect())
        self._identity = None

    def snapshot(self, now_ms=None):
        request = Request(self._url, headers={'X-Polybot-Token': self._token}, method='GET')
        with self._opener.open(request, timeout=self._timeout) as response:
            if response.status != 200:
                raise ValueError('Snapshot unavailable')
            raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('Snapshot exceeds size bound')
        snapshot = validate(decode(raw), now_ms)
        identity = (snapshot['sessionId'], snapshot['account']['id'], int(snapshot['sequence']), int(snapshot['inputMs']))
        if self._identity and (identity[:2] != self._identity[:2]
                              or identity[2] < self._identity[2] or identity[3] < self._identity[3]):
            raise ValueError('Account/session changed or causal clock regressed; start a new run')
        self._identity = identity
        return snapshot
