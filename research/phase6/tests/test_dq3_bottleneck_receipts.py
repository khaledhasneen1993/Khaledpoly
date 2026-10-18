import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.phase6.dq3_bottleneck_receipts import selection,summarize,collect,traffic,ROOT


class Dq3BottleneckTest(unittest.TestCase):
    def test_complete_primary_leg_selection_never_claims_actual_order(self):
        s=selection()
        self.assertEqual(s['state']['originalSequence'],197690);self.assertEqual(s['targetQuote']['price'],'0.47')
        self.assertEqual(len(s['transactions']),8);self.assertEqual(s['otherLegObservationsNotAudited'],47)
        self.assertFalse(s['actualOrderOrObservedActivationClaimed']);self.assertTrue(s['relaxedUpperBoundNotActualLifecycle'])
        for x in s['transactions']:
            self.assertLess(x['sample']['arrivalMs'],s['terminalMs'])
            self.assertGreaterEqual(int(x['sample']['timestamp']),s['state']['activationDueMs'])

    def test_exact_complete_traffic_artifact_scope_and_overlaps(self):
        import json
        r=traffic();original=json.loads((ROOT/'traffic-selection.json').read_text())
        self.assertEqual([s['selection'] for s in r['states']],original)
        self.assertTrue(all(s['anchorSeen'] for s in r['states']))
        observations=[o for s in r['states'] for o in s['observations']]
        self.assertEqual(len(observations),823);self.assertEqual(r['observationCount'],823)
        txs=sorted({o['sample']['transaction_hash'] for o in observations})
        self.assertEqual(txs,r['uniqueTransactionHashes']);self.assertEqual(len(txs),416)
        self.assertTrue(r['activationIsRelaxedDueTimeUpperBoundNotObserved'])
        self.assertFalse(r['actualQueueOrCandidateTrajectorySimulated']);self.assertFalse(r['netPnlRecomputed'])
        self.assertEqual(r['fillsCreated'],0)

    def report(self,s):
        parts=[dict(makerToken=s['targetQuote']['token'],makerSide='BUY',sharesRaw=1000000,collateralRaw=480000,makerPrice='.48')]
        group=dict(components=parts,routeSharesRaw={'MINT':1000000})
        return dict(complete=True,results=[dict(sample=x['sample'],routeConservation=dict(uniqueConservedGroup=True,matchingGroups=[copy.deepcopy(group)])) for x in s['transactions']])

    def test_integer_components_not_public_price_and_no_queue_or_profit_inference(self):
        s=selection();r=self.report(s);z=summarize(r,s)
        self.assertEqual(z['targetBuyAtOrBelowOwnBidSharesRaw'],0);self.assertEqual(z['fillsCreated'],0)
        self.assertFalse(z['observedActivationOrQueueProven']);self.assertFalse(z['netPnlRecomputed'])
        r['results'][0]['routeConservation']['matchingGroups'][0]['components'][0]['collateralRaw']=460000
        self.assertEqual(summarize(r,s)['targetBuyAtOrBelowOwnBidSharesRaw'],1000000)
        r['results'][0]['routeConservation']['uniqueConservedGroup']=False
        with self.assertRaisesRegex(ValueError,'ambiguous'):summarize(r,s)

    def test_public_read_budget_block_cache_and_same_selection_resume(self):
        s=selection();expected=self.report(s)
        def read(method,args):
            if method=='eth_chainId':return '0x89'
            if method=='eth_getTransactionReceipt':return dict(transactionHash=args[0],blockHash='0xabc')
            if method=='eth_getBlockByHash':return dict(hash='0xabc')
            raise AssertionError('Unexpected RPC method')
        def decoded(sample,*args):return dict(sample=sample)
        def conserved(result,pair):return expected['results'][0]['routeConservation']
        with tempfile.TemporaryDirectory() as d,patch('research.phase6.dq3_bottleneck_receipts.corroborate',side_effect=decoded),patch('research.phase6.dq3_bottleneck_receipts.routes',side_effect=conserved),patch('research.phase6.dq3_bottleneck_receipts.time.sleep'):
            collect(s,d,read=read,topics={'fixture':'yes'})
            import json
            report=json.loads((Path(d)/'report.json').read_text())
            self.assertEqual(report['rpcCalls'],dict(eth_chainId=1,eth_getTransactionReceipt=8,eth_getBlockByHash=1))
            collect(s,d,read=read,topics={'fixture':'yes'})
            self.assertEqual(json.loads((Path(d)/'report.json').read_text())['rpcCalls'],dict(eth_chainId=1))
            bad=dict(s,scope='changed')
            with self.assertRaisesRegex(ValueError,'resume'):collect(bad,d,read=read,topics={'fixture':'yes'})


if __name__=='__main__':unittest.main()
