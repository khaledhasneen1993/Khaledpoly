import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.phase6.queue_aware_post_gap_result import verify,ROOT
from research.phase6.queue_aware_recovery_receipts import selection,collect,decode


class RecoveryTest(unittest.TestCase):
    def test_complete_stream_and_all451_no_execution_or_price_filter(self):
        r=verify();self.assertEqual(r['retainedRecords'],20691);self.assertEqual(r['originalPairObservations'],451)
        self.assertEqual(r['firstFreshBothBookNonemptyFrame'],dict(seq=260664,at=1792269760875))
        self.assertEqual(r['uniqueScopedGapFrames'],15);self.assertFalse(r['candidateAccountSimulated'])
        s=selection();self.assertEqual(len({t['transactionHash'] for t in s['transactions']}),451)
        self.assertTrue(s['selectionNotFilteredByPriceOrOutcome']);self.assertFalse(s['netPnlRecomputed'])

    def test_budget_changed_checkpoint_and_wrong_chain_fail_before_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'budget'):collect(dict(maxNewReceiptRequests=452,transactions=[]),temp)
            spec=dict(maxNewReceiptRequests=451,transactions=[dict(transactionHash=str(i)) for i in range(451)],pair=['a','b'])
            Path(temp,'selection.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'selection'):collect(spec,temp)
        with tempfile.TemporaryDirectory() as temp,patch('research.phase6.queue_aware_recovery_receipts.cached',return_value={'old':dict(topics={})}):
            with self.assertRaisesRegex(ValueError,'chain'):collect(spec,temp,read=lambda method,args:'0x1')
            self.assertFalse(Path(temp,'report.json').exists())

    def test_unknown_route_not_zero_and_raw_context_mutation_rejected(self):
        with patch('research.phase6.queue_aware_recovery_receipts.corroborate',return_value={}),patch('research.phase6.queue_aware_recovery_receipts.routes',return_value=dict(uniqueConservedGroup=False)):
            with self.assertRaisesRegex(ValueError,'never zero'):decode(dict(sample={}),dict(receipt={},block={}),{},['a','b'])
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            for name in ['artifact-manifest.json','context-manifest.json','data-summary.json']:(p/name).write_bytes((ROOT/name).read_bytes())
            (p/'context.records.jsonl.gz').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'artifact member'):verify(p)


if __name__=='__main__':unittest.main()
