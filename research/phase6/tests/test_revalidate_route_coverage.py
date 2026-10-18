from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.phase6.revalidate_route_coverage import ARCHIVE, revalidate


class ArchivedRouteCoverageTest(unittest.TestCase):
    def test_original_twenty_redecode_offline(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('Network forbidden')):
            report = revalidate()
        self.assertEqual(report['verifiedTransactions'], 20)
        self.assertEqual(report['cohorts']['ENTRY_BASELINE_4']['routeSharesRaw'],
                         {'MINT': 922000000, 'DIRECT': 78000000})
        exit = report['cohorts']['MAKER_EXIT_LABELLED_14']
        self.assertEqual(exit['routeSharesRaw'], {'MINT': 79315186, 'DIRECT': 55570000})
        self.assertEqual(len(exit['tokens']), 1)  # First ten omit the own-token fill triggers.
        self.assertEqual(report['fillsCreated'], 0)
        self.assertEqual(report['networkRequests'], 0)
        self.assertFalse(report['netPnlRecomputed'])

    def test_changed_evidence_fails_hash_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.b64'
            data = ARCHIVE.read_bytes()
            path.write_bytes((b'A' if data[:1] != b'A' else b'B') + data[1:])
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                revalidate(path)
