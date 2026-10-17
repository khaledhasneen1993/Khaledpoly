"""Crash/resume and hostile external input must never bypass Java PAPER screening."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'research'/'phase3'/'tests'))
from test_research import fixture, BASE
from research.phase6.external_strategy import ExternalStrategyReview
from research.phase6.paper_screen_bridge import DurablePaperScreen, digest

def envelope():
    return {'schema':1,'version':'1.0','strategyId':'research-probe',
            'sessionId':'fixture','accountId':'paper-default','snapshotSequence':1,
            'observedMs':BASE,
            'proposals':[{'id':'a','edge':'.04',
                'legs':[{'condition':'market','token':'a','buy':True,
                         'price':'.41','size':'5','expiresMs':BASE+250}]}]}

class FakeClient:
    def __init__(self,obs):
        self.obs=obs
        self.saved={}
        self.posts=0
        self.gets=0
        self.drop=False

    def snapshot(self,now_ms=None):
        return self.obs

    def screen_identical(self,proposal):
        self.posts+=1
        receipt={'id':proposal['id'],'status':'SCREENED_SHADOW_ONLY',
                 'sequence':proposal['sequence'],'expiresMs':BASE+250,
                 'decision':'NO_GO','executionEnabled':False,'liveAllowed':False}
        self.saved[proposal['id']]=receipt
        if self.drop:
            raise TimeoutError('Response lost after Java committed durable inbox')
        return receipt

    def saved_receipt(self,proposal):
        self.gets+=1
        return self.saved.get(proposal['id'])


class BridgeTest(unittest.TestCase):
    def test_java_request_stays_screen_only_and_replay_is_read_only(self):
        f=fixture()
        client=FakeClient(f)
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'outbox'
            one=DurablePaperScreen(client).run(target,f,envelope(),at_ms=BASE)
            self.assertEqual(one['confirmedScreenReceipts'],1)
            self.assertEqual(one['paperReservationsMade'],False)
            self.assertEqual(one['venueOrdersSubmitted'],0)
            self.assertEqual(client.posts,1)
            second=DurablePaperScreen(client).run(target,f,envelope(),at_ms=BASE)
            self.assertEqual(second['confirmedScreenReceipts'],1)
            self.assertFalse(second['firstRun'])
            self.assertEqual(client.posts,1)
            self.assertEqual(client.gets,0)
            self.assertTrue(next(target.glob('request-*.json')).exists())

    def test_lost_receipt_recovers_only_from_durable_get(self):
        obs=fixture()
        client=FakeClient(obs)
        client.drop=True
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'outbox'
            first=DurablePaperScreen(client).run(out,obs,envelope(),at_ms=BASE)
            self.assertEqual(first['unknownRemoteReceipts'],1)
            client.drop=False
            second=DurablePaperScreen(client).run(out,obs,envelope(),at_ms=BASE)
            self.assertEqual(second['confirmedScreenReceipts'],1)
            self.assertEqual(client.posts,1)
            self.assertEqual(client.gets,1)
            self.assertEqual(list(out.glob('receipt-*.json'))[0].name,'receipt-0001.json')

    def test_old_snapshot_may_only_recover_durable_receipt_not_post(self):
        obs=fixture()
        client=FakeClient(obs)
        client.drop=True
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'outbox'
            DurablePaperScreen(client).run(folder,obs,envelope(),at_ms=BASE)
            client.drop=False
            recovered=DurablePaperScreen(client).run(
                folder,obs,envelope(),at_ms=BASE+86400000)
            self.assertEqual(recovered['confirmedScreenReceipts'],1)
            self.assertEqual(client.posts,1)
            with self.assertRaisesRegex(ValueError,'Stale'):
                DurablePaperScreen(FakeClient(obs)).run(
                    Path(d)/'new-session',obs,envelope(),at_ms=BASE+86400000)

    def test_unknown_get_never_reissues_post_or_creates_new_id(self):
        obs=fixture()
        client=FakeClient(obs)
        client.drop=True
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'outbox'
            DurablePaperScreen(client).run(out,obs,envelope(),at_ms=BASE)
            client.saved.clear()
            client.drop=False
            result=DurablePaperScreen(client).run(out,obs,envelope(),at_ms=BASE)
            self.assertEqual(result['unknownRemoteReceipts'],1)
            self.assertEqual(client.posts,1)

    def test_changed_snapshot_and_tampered_manifest_fail_closed(self):
        obs=fixture()
        client=FakeClient(obs)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'outbox'
            DurablePaperScreen(client).run(out,obs,envelope(),at_ms=BASE)
            modified=envelope()
            modified['proposals'][0]['edge']='.07'
            with self.assertRaisesRegex(ValueError,'Outbox'):
                DurablePaperScreen(client).run(out,obs,modified,at_ms=BASE)
            next_obs=fixture()
            next_obs['account']['halted']=True
            with self.assertRaisesRegex(ValueError,'Outbox'):
                DurablePaperScreen(client).run(out,next_obs,envelope(),at_ms=BASE)
            self.assertEqual(client.posts,1)

    def test_remote_changes_before_first_submission_fails(self):
        obs=fixture()
        client=FakeClient(fixture())
        client.obs['account']['halted']=True
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'snapshot changed'):
                DurablePaperScreen(client).run(Path(d)/'outbox',obs,envelope(),at_ms=BASE)
            self.assertEqual(client.posts,0)

    def test_different_accounts_have_different_remote_identifiers(self):
        a=fixture()
        b=fixture()
        b['sessionId']='other-session'
        b['account']['id']='another-paper'
        a_request=envelope()
        b_request=envelope()
        b_request.update(sessionId=b['sessionId'],accountId=b['account']['id'])
        ra=ExternalStrategyReview().review(a,a_request,at_ms=BASE)
        rb=ExternalStrategyReview().review(b,b_request,at_ms=BASE)
        self.assertNotEqual(ra['approvedPaperScreenRequests'][0]['id'],
                            rb['approvedPaperScreenRequests'][0]['id'])
        self.assertNotIn('privateKey',str(ra))
        self.assertEqual(digest(a),digest(fixture()))


if __name__=='__main__':
    unittest.main()
