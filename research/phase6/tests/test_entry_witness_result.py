import copy
import json
from decimal import Decimal
from pathlib import Path
import unittest
from research.phase6.entry_witness_result import analyze,load,verify_rows,ROOT


class EntryWitnessResultTest(unittest.TestCase):
    def test_original_account_and_actual_risk_reasons_reproduce(self):
        r=analyze()
        self.assertEqual(r['originalFieldsReproduced'],69);self.assertTrue(r['originalAuditActionsReproduced'])
        self.assertEqual(r['windowsCovered'],6);self.assertEqual(r['witnessCount'],34)
        self.assertEqual(r['actualBranchCounts'],dict(MIN_SIZE_AND_NET_EDGE=16,PAIR_SUBMITTED=1,RESTING=2,MIN_SIZE=3,NET_EDGE=12))
        self.assertEqual(r['minSizeRejections'],19);self.assertEqual(r['insufficientEdgeRejections'],28)
        self.assertEqual(r['accountNetPnl'],0);self.assertFalse(r['fillsInferred'])

    def test_changed_threshold_size_or_missing_window_rejected(self):
        r=json.loads(load()['report.json'],parse_float=Decimal)
        rows=r['entryDecisionWitnesses'];cfg=json.loads(Path('research/phase2/research-config.json').read_text())
        windows=json.loads((ROOT/'windows.json').read_text())
        for key in ('requiredEdge','quantity','netEdgeTotal'):
            bad=copy.deepcopy(rows);bad[0][key]=999
            with self.assertRaises(ValueError):verify_rows(bad,cfg,windows)
        with self.assertRaisesRegex(ValueError,'no decision'):verify_rows(rows,cfg,windows+[dict(condition='absent',startMs=0,endMs=1)])


if __name__=='__main__':unittest.main()
