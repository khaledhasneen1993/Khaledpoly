import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.phase6.dq3_receipt_coverage import (ROOT,traffic,cached_receipts,coverage,
    next_selection,component_volume,collect)


class ReceiptCoverageTest(unittest.TestCase):
    def test_exact_cached_overlap_and_missing_is_unknown_not_zero(self):
        cache=cached_receipts();r=coverage(cache)
        self.assertEqual(len(cache),10);self.assertEqual(len(r['legs']),22)
        complete=[l for l in r['legs'] if l['complete']]
        self.assertEqual([(l['originalSequence'],l['observationCount']) for l in complete],
                         [(173342,1),(197690,8),(198832,4)])
        self.assertTrue(all(l['actualPriceCompatibleSharesRaw']==0 for l in complete))
        self.assertTrue(all(l['actualPriceCompatibleSharesRaw'] is None for l in r['legs'] if not l['complete']))
        self.assertFalse(r['netPnlRecomputed']);self.assertEqual(r['fillsCreated'],0)
        self.assertEqual(r,json.loads((ROOT/'cached-overlap-coverage.json').read_text()))

    def test_next_scope_chronological_complete_leg_not_profit_selected(self):
        s=next_selection(cached_receipts())
        self.assertEqual(s['state']['originalSequence'],243583)
        self.assertEqual(s['targetQuote']['price'],'0.49')
        self.assertEqual(s['maxNewReceiptRequests'],39);self.assertEqual(len(s['transactions']),39)
        self.assertEqual(len({t['transactionHash'] for t in s['transactions']}),39)
        self.assertEqual(s,json.loads((ROOT/'overlap-selection.json').read_text()))
        self.assertFalse(s['actualOrderOrObservedActivationClaimed'])
        changed=copy.deepcopy(s);changed['targetQuote']['price']='0.50'
        o=next(o for st in traffic()['states'] if st['selection']['originalSequence']==243583
               for o in st['observations'] if o['targetToken']==s['targetQuote']['token'])
        with self.assertRaisesRegex(ValueError,'binding'):component_volume(o,changed['targetQuote'],{})

    def test_request_budget_and_resume_without_public_network(self):
        s=next_selection(cached_receipts())
        def read(method,args):
            if method=='eth_chainId':return '0x89'
            if method=='eth_getTransactionReceipt':return dict(transactionHash=args[0],blockHash='0xabc')
            if method=='eth_getBlockByHash':return dict(hash='0xabc')
            raise AssertionError('Unexpected method')
        with tempfile.TemporaryDirectory() as d,patch('research.phase6.dq3_receipt_coverage.time.sleep'),patch('research.phase6.dq3_receipt_coverage.component_volume',return_value=0):
            collect(s,d,read=read,topics={'mock':True})
            r=json.loads((Path(d)/'report.json').read_text())
            self.assertEqual(r['rpcCalls'],dict(eth_chainId=1,eth_getTransactionReceipt=39,eth_getBlockByHash=1))
            collect(s,d,read=read,topics={'mock':True})
            self.assertEqual(json.loads((Path(d)/'report.json').read_text())['rpcCalls'],dict(eth_chainId=1))
            with self.assertRaisesRegex(ValueError,'resume'):collect(dict(s,scope='changed'),d,read=read,topics={'mock':True})


if __name__=='__main__':unittest.main()
