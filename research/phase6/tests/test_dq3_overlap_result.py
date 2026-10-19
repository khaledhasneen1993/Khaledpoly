"""Immutable complete39-receipt proof, no network or economic qualification."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from research.phase6.dq3_receipt_coverage import ROOT,cached_receipts,coverage,next_selection,collect


class OverlapResultTest(unittest.TestCase):
    def test_all_original_receipts_redecode_and_exact_overlapping_coverage(self):
        raw=base64.b64decode((ROOT/'overlap-result/artifact.zip.b64').read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'baade0bae80c97677a4a4109da1bbf153e8445631e936e47aa6fc563d6caa621')
        evidence=cached_receipts();spec=next_selection(evidence)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertEqual(len(z.infolist()),42)
            self.assertEqual(json.loads(z.read('selection.json')),spec)
            report=json.loads(z.read('report.json'))
            self.assertTrue(report['complete']);self.assertEqual(report['errors'],[])
            self.assertEqual(report['rpcCalls'],dict(eth_chainId=1,eth_getTransactionReceipt=39,eth_getBlockByHash=8))
            self.assertFalse(report['netPnlRecomputed']);self.assertFalse(report['liveAllowed'])
            for t in spec['transactions']:
                tx=t['transactionHash'];self.assertNotIn(tx,evidence)
                data=json.loads(z.read('raw/'+tx+'.json'))
                evidence[tx]=dict(data=data,topics=report['eventTopics'])
            actual=coverage(evidence)  # Re-decodes/conserves actual components for EVERY covered observation.
            self.assertEqual(actual,json.loads(z.read('coverage.json')))
            self.assertEqual(actual,json.loads((ROOT/'overlap-result/coverage.json').read_text()))
        self.assertEqual(actual['receiptCacheTransactions'],49)
        complete=[l for l in actual['legs'] if l['complete']]
        self.assertEqual(len(complete),10)
        positive=[l for l in complete if l['actualPriceCompatibleSharesRaw']>0]
        self.assertEqual([l['originalSequence'] for l in positive],[243583,245065,246180])
        self.assertTrue(all(l['actualPriceCompatibleSharesRaw']==960720922 for l in positive))
        self.assertEqual(sum(l['completeWindowZeroActualPricedComponents'] for l in complete),7)
        self.assertFalse(actual['queueOrObservedActivationProven']);self.assertEqual(actual['fillsCreated'],0)
        self.assertTrue(all(l['actualPriceCompatibleSharesRaw'] is None for l in actual['legs'] if not l['complete']))

    def test_missing_receipts_never_become_complete_zero_evidence(self):
        spec=next_selection(cached_receipts())
        def absent(method,args):
            if method=='eth_chainId':return '0x89'
            if method=='eth_getTransactionReceipt':return None
            raise AssertionError('Should not request block for absent receipt')
        with tempfile.TemporaryDirectory() as d,patch('research.phase6.dq3_receipt_coverage.time.sleep'):
            with self.assertRaisesRegex(ValueError,'Incomplete receipt cohort'):
                collect(spec,d,read=absent,topics={'fixture':True})
            report=json.loads((Path(d)/'report.json').read_text())
            self.assertFalse(report['complete']);self.assertEqual(len(report['errors']),39)
            self.assertEqual(report['rpcCalls']['eth_getTransactionReceipt'],39)
            self.assertEqual(json.loads((Path(d)/'coverage.json').read_text()),coverage(cached_receipts()))


if __name__=='__main__':unittest.main()
