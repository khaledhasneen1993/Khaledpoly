import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.phase6.compare_frozen_label_variants import run


class FrozenLabelControlTest(unittest.TestCase):
    def test_changed_frozen_source_stops_before_output_or_account_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.write_text('changed')
            freeze=root/'freeze.json';freeze.write_text(json.dumps(dict(filesSha256={str(source):hashlib.sha256(b'original').hexdigest()})))
            with patch('research.phase6.compare_frozen_label_variants.subprocess.run') as execute:
                with self.assertRaisesRegex(ValueError,'Frozen label control changed'):
                    run(root/'tape',root/'output',freeze)
                execute.assert_not_called()
            self.assertFalse((root/'output').exists())
