import gzip
from pathlib import Path
import tempfile
import unittest
from research.phase3.polybot_sdk.tapes import open_tape,recorded_tapes

class CompressedTapeTest(unittest.TestCase):
    def test_transport_roundtrip_and_both_formats_discovered(self):
        with tempfile.TemporaryDirectory() as root:
            run=Path(root)/'run';run.mkdir();raw=b'{"kind":"RUN_END","data":{"complete":true}}\n'
            plain=run/'events.jsonl';compressed=run/'events.jsonl.gz'
            plain.write_bytes(raw)
            with gzip.open(compressed,'wb') as stream:stream.write(raw)
            self.assertEqual(recorded_tapes(root),sorted([plain,compressed]))
            for path in (plain,compressed):
                with open_tape(path,'rb') as stream:self.assertEqual(stream.read(),raw)
                with open_tape(path,'rt') as stream:self.assertEqual(stream.read(),raw.decode())
            with self.assertRaises(ValueError):open_tape(plain,'w')
    def test_truncated_gzip_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'events.jsonl.gz';path.write_bytes(gzip.compress(b'not a clean tape')[:-5])
            with self.assertRaises((EOFError,OSError)):
                with open_tape(path) as stream:stream.read()
