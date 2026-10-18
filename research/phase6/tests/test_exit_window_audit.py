import base64
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from research.phase6.exit_window_audit import ROOT,validate,seed_cache,collect_window


class ExitWindowAuditTest(unittest.TestCase):
    def fixture(self):
        return json.loads((ROOT/'selection.json').read_text()),json.loads(gzip.decompress(base64.b64decode((ROOT/'original-frames.json.gz.b64').read_bytes())))

    def test_all_nine_bindings_include_later_replacement_without_changing_actual_terminal(self):
        selection,frames=self.fixture();validate(selection,frames)
        self.assertEqual(selection['originalObservedOrderDiagnostic']['terminalMs'],1792269695069)
        self.assertEqual(selection['sevenLabelReplayTerminalMs'],1792269695159)
        self.assertEqual(selection['window']['endExclusiveMs'],1792269696284)
        self.assertIn(154084,[x['normalizedSeq'] for x in selection['transactions']])

    def test_raw_tamper_and_window_end_are_rejected(self):
        for mutation in ('raw','window'):
            selection,frames=self.fixture()
            if mutation=='raw':frames[0]['raw']['arrivalMs']+=1
            else:selection['window']['endExclusiveMs']=selection['transactions'][-1]['sample']['arrivalMs']
            with self.assertRaises(ValueError):validate(selection,frames)

    def test_original_two_cached_receipts_and_changed_resume_fail_before_network(self):
        selection,frames=self.fixture()
        with tempfile.TemporaryDirectory() as folder:
            seed_cache(folder,selection);seed_cache(folder,selection)
            self.assertEqual(len(list((Path(folder)/'raw').glob('*.json'))),2)
            (Path(folder)/'selection.json').write_text('{}')
            read=Mock()
            with self.assertRaisesRegex(ValueError,'Resume window'):
                collect_window(selection,frames,folder,topics={'filled':'x','matched':'y'},read=read)
            read.assert_not_called()
