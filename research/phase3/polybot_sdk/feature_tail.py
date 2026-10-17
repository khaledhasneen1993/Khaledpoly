"""Bounded incremental input, retaining partial lines until they are fully available."""
from pathlib import Path
from .features import Observation
from .model import decode


class FeatureTail:
    def __init__(self, path):
        self.path = Path(path)
        self.identity, self.offset = None, 0

    def update(self, store, maximum_rows=10000):
        stat = self.path.stat()
        identity = stat.st_dev, stat.st_ino
        if self.identity is not None and (self.identity != identity or stat.st_size < self.offset):
            raise ValueError('Feature input rotated or truncated; start a new run')
        self.identity = identity
        count = 0
        with self.path.open('rb') as stream:
            stream.seek(self.offset)
            while count < maximum_rows:
                raw = stream.readline(65537)
                if len(raw) > 65536:
                    raise ValueError('Feature row exceeds 64 KiB')
                if not raw or not raw.endswith(b'\n'):
                    break
                store.add(Observation.parse(decode(raw)))
                self.offset = stream.tell()
                count += 1
            if count == maximum_rows and stream.read(1):
                raise ValueError('Feature input exceeds per-cycle processing bound')
        return count
