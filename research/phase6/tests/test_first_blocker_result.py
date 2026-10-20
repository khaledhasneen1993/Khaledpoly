import copy
import json
import unittest
from research.phase6.first_blocker_result import load,verify

class FirstBlockerResultTest(unittest.TestCase):
    def test_all_actual_integer_components_rederived(self):
        r=verify(*load());self.assertEqual(r['conservedMakerComponents'],16)
        self.assertEqual(r['venueSharesRaw'],200000000);self.assertEqual(r['takerCollateralRaw'],114000000)
        self.assertEqual(r['routeSharesRaw'],{'DIRECT':55000000,'MINT':145000000})
        self.assertFalse(r['nativePoolExtended']);self.assertFalse(r['counterfactualQueueAllocationProven'])

    def test_route_or_raw_change_rejected(self):
        s,raw,p=load();bad=copy.deepcopy(p);bad['route']['matchingGroups'][0]['components'][0]['sharesRaw']+=1
        with self.assertRaisesRegex(ValueError,'components'):verify(s,raw,bad)
        with self.assertRaisesRegex(ValueError,'provenance'):verify(s,raw+b' ',p)

    def test_no_account_promotion_or_larger_request_budget(self):
        s,raw,p=load()
        for key in ('candidateAccountSimulated','marketNetPnlRecomputed','liveAllowed'):
            bad=copy.deepcopy(p);bad[key]=True
            with self.assertRaisesRegex(ValueError,'evidence'):verify(s,raw,bad)
        bad=copy.deepcopy(p);bad['rpcCalls']['eth_getTransactionReceipt']=2
        with self.assertRaisesRegex(ValueError,'provenance'):verify(s,raw,bad)

if __name__=='__main__':unittest.main()
