"""Historical evidence only: verify two pinned original sources, never current replay code."""
import base64
import gzip
import hashlib
import json
from pathlib import Path

ARCHIVE=Path('research/experiments/residual-entry-risk-20261018/historical-sources.json.gz.b64')


def verify_historical_sources(frozen,archive=ARCHIVE):
    raw=base64.b64decode(b''.join(Path(archive).read_bytes().split()),validate=True)
    if hashlib.sha256(raw).hexdigest()!='ee7541f7755c53deaf4c05addce714e57f6e3bb4f29d7e9f089e5e8dd0aa8b81':
        raise ValueError('Pinned historical source archive changed')
    bundle=json.loads(gzip.decompress(raw))
    if bundle['sourceCommit']!='d25c19a13afb55f8413af3d61846f8d4e666bd3c':
        raise ValueError('Unexpected historical source commit')
    for path,digest in frozen['filesSha256'].items():
        # Only the exact two archived original Java sources may use history.
        data=bundle['files'][path].encode() if path in bundle['files'] else Path(path).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('Historical source/config/acceptance hash differs: '+path)
