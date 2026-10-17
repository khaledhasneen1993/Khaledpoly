"""Untrusted strategy envelopes cannot sign, cross accounts or skip risk."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'research'/'phase3'/'tests'))
from test_research import fixture, BASE
from research.phase6.external_strategy import ExternalStrategyReview

def envelope():
    return {'schema':1,'version':'1.0','strategyId':'external-paper',
            'sessionId':'fixture','accountId':'paper-default','snapshotSequence':1,
            'observedMs':BASE,
            'proposals':[{'id':'strategy:market:a','edge':'.04',
                'legs':[{'condition':'market','token':'a','buy':True,
                         'price':'.41','size':'5','expiresMs':BASE+250}]}]}


class StrategyBoundaryTest(unittest.TestCase):
    def test_valid_paper_group_only_reads_existing_risk(self):
        e=ExternalStrategyReview()
        obs=fixture()
        a=e.review(obs,envelope(),at_ms=BASE)
        self.assertEqual(a['admittedResearchCandidates'],1)
        self.assertEqual(a['venueOrdersSubmitted'],0)
        self.assertFalse(a['accountBalancesModified'])
        self.assertFalse(a['liveAllowed'])
        replay=e.review(obs,envelope(),at_ms=BASE)
        self.assertTrue(replay['replayedIdentical'])

    def test_account_identity_and_conflicting_replay_rejected(self):
        e=ExternalStrategyReview()
        bad=envelope()
        bad['accountId']='other'
        with self.assertRaisesRegex(ValueError,'mixed accounts'):
            e.review(fixture(),bad,at_ms=BASE)
        e.review(fixture(),envelope(),at_ms=BASE)
        changed=envelope()
        changed['proposals'][0]['edge']='.1'
        with self.assertRaisesRegex(ValueError,'idempotency'):
            e.review(fixture(),changed,at_ms=BASE)

    def test_unsafe_fields_cannot_bypass_virtual_allocator(self):
        e=ExternalStrategyReview()
        input=envelope()
        input['privateKey']='not a valid field'
        with self.assertRaisesRegex(ValueError,'Unexpected'):
            e.review(fixture(),input,at_ms=BASE)
        input=envelope()
        input['proposals'][0]['legs'][0]['price']='.61'
        result=e.review(fixture(),input,at_ms=BASE)
        self.assertEqual(result['admittedResearchCandidates'],0)
        self.assertGreater(len(result['rejections']),0)

    def test_blocked_account_and_bad_global_gate_cannot_submit(self):
        blocked=fixture()
        blocked['account']['halted']=True
        e=ExternalStrategyReview()
        result=e.review(blocked,envelope(),at_ms=BASE)
        self.assertEqual(result['admittedResearchCandidates'],0)
        with self.assertRaises(PermissionError):
            e.review(fixture(),envelope(),at_ms=BASE,account_gate={
                'scope':'READ_ONLY_CROSS_ACCOUNT_PAPER_RISK_GATE',
                'mayStudyPaperProposals':False,'mayReserveOrSubmit':False,
                'liveAllowed':False})
        # The same session/sequence may never be reused with changed
        # account state; only an independent new reviewer can study it.
        with self.assertRaisesRegex(ValueError,'idempotency'):
            e.review(fixture(),envelope(),at_ms=BASE)
        self.assertEqual(ExternalStrategyReview().review(
            fixture(),envelope(),at_ms=BASE)['admittedResearchCandidates'],1)


if __name__=='__main__':
    unittest.main()
