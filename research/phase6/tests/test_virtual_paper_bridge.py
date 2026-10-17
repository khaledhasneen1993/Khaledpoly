"""Durable virtual PAPER orders: no execution without flag or Java consent."""
from pathlib import Path
import sys
import tempfile
import unittest
import fcntl
import os

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'research'/'phase3'/'tests'))
from test_research import fixture, BASE
from research.phase6.virtual_paper_bridge import DurableVirtualPaperOrders

def observation():
    v=fixture()
    v['paperExecutionEnabled']=True
    return v

def envelope():
    return {'schema':1,'version':'1.0','strategyId':'paper-ledger-test',
            'sessionId':'fixture','accountId':'paper-default',
            'snapshotSequence':1,'observedMs':BASE,
            'proposals':[{'id':'a','edge':'.04',
                'legs':[{'condition':'market','token':'a','buy':True,
                         'price':'.41','size':'5','expiresMs':BASE+250}]}]}

class FakeLedgerClient:
    def __init__(self,obs):
        self.obs=obs
        self.calls=0
        self.ledger={}
        self.lose_reply=False
    def snapshot(self,now_ms=None):
        return self.obs
    def retry_identical(self,request):
        self.calls+=1
        id=request['id']
        if id in self.ledger:
            old=self.ledger[id]
            assert request==old, 'Conflicting Java reservation ID'
            return {'id':id,'status':'PAPER_ALREADY_RECORDED','virtualOnly':True,
                    'executionEnabled':False,'liveAllowed':False}
        self.ledger[id]=request
        if self.lose_reply:
            raise TimeoutError('Java persisted reservation, response lost')
        return {'id':id,'status':'PAPER_SUBMITTED','virtualOnly':True,
                'executionEnabled':False,'liveAllowed':False}

class VirtualPaperIntegrationTest(unittest.TestCase):
    def test_disabled_by_default_and_requires_java_paper_enable(self):
        obs=observation()
        client=FakeLedgerClient(obs)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'out'
            with self.assertRaises(PermissionError):
                DurableVirtualPaperOrders(client).run(path,obs,envelope(),at_ms=BASE)
            self.assertFalse(path.exists())
            obs['paperExecutionEnabled']=False
            with self.assertRaisesRegex(PermissionError,'executor'):
                DurableVirtualPaperOrders(client).run(
                    path,obs,envelope(),enable_virtual=True,at_ms=BASE)
            self.assertEqual(client.calls,0)

    def test_explicit_paper_order_uses_original_central_ledger_once(self):
        obs=observation()
        client=FakeLedgerClient(obs)
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'out'
            first=DurableVirtualPaperOrders(client).run(
                target,obs,envelope(),enable_virtual=True,at_ms=BASE)
            self.assertEqual(first['receiptCounts']['PAPER_SUBMITTED'],1)
            self.assertEqual(len(client.ledger),1)
            self.assertFalse(first['realOrdersEnabled'])
            next=DurableVirtualPaperOrders(client).run(
                target,obs,envelope(),enable_virtual=True,at_ms=BASE)
            self.assertEqual(next['receiptCounts']['PAPER_SUBMITTED'],1)
            self.assertEqual(client.calls,1)

    def test_lost_response_replays_identical_id_not_another_reservation(self):
        obs=observation()
        client=FakeLedgerClient(obs)
        client.lose_reply=True
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out'
            first=DurableVirtualPaperOrders(client).run(
                out,obs,envelope(),enable_virtual=True,at_ms=BASE)
            self.assertEqual(first['unknownOutcomes'],1)
            self.assertEqual(len(client.ledger),1)
            client.lose_reply=False
            # A real PAPER executor advances its receipt clock after time
            # passes while retaining the same account/session identity.
            client.obs=observation()
            client.obs['inputMs']=BASE+100000
            client.obs['generatedMs']=BASE+100000
            client.obs['sequence']=2
            client.obs['markets'][0]['observedMs']=BASE+100000
            for book in client.obs['books'].values():
                book['sourceMs']=BASE+100000
                book['receivedMs']=BASE+100000
            second=DurableVirtualPaperOrders(client).run(
                out,obs,envelope(),enable_virtual=True,at_ms=BASE+100000)
            self.assertEqual(second['receiptCounts']['PAPER_ALREADY_RECORDED'],1)
            self.assertEqual(len(client.ledger),1)
            self.assertEqual(client.calls,2)

    def test_wrong_account_session_or_changed_envelope_refused(self):
        obs=observation()
        client=FakeLedgerClient(obs)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out'
            first=DurableVirtualPaperOrders(client).run(
                out,obs,envelope(),enable_virtual=True,at_ms=BASE)
            mutated=envelope()
            mutated['proposals'][0]['edge']='.12'
            with self.assertRaisesRegex(ValueError,'outbox'):
                DurableVirtualPaperOrders(client).run(
                    out,obs,mutated,enable_virtual=True,at_ms=BASE)
            other=observation()
            other['sessionId']='new-session'
            client.obs=other
            self.assertEqual(first['receiptCounts']['PAPER_SUBMITTED'],1)
            self.assertEqual(len(client.ledger),1)

    def test_pending_virtual_order_cannot_replay_to_new_account_session(self):
        obs=observation()
        client=FakeLedgerClient(obs)
        client.lose_reply=True
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out'
            initial=DurableVirtualPaperOrders(client).run(
                out,obs,envelope(),enable_virtual=True,at_ms=BASE)
            self.assertEqual(initial['unknownOutcomes'],1)
            client.lose_reply=False
            changed=observation()
            changed['sessionId']='different-executor-session'
            client.obs=changed
            with self.assertRaisesRegex(ValueError,'Changed PAPER'):
                DurableVirtualPaperOrders(client).run(
                    out,obs,envelope(),enable_virtual=True,at_ms=BASE)
            self.assertEqual(client.calls,1)
            self.assertEqual(len(client.ledger),1)

    def test_multiple_independent_intents_require_new_causal_snapshot(self):
        obs=observation()
        client=FakeLedgerClient(obs)
        proposed=envelope()
        proposed['proposals'].append({
            'id':'b','edge':'.03',
            'legs':[{'condition':'market','token':'b','buy':True,
                     'price':'.41','size':'5','expiresMs':BASE+250}]
        })
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'out'
            with self.assertRaisesRegex(ValueError,'one atomic virtual PAPER'):
                DurableVirtualPaperOrders(client).run(
                    target,obs,proposed,enable_virtual=True,at_ms=BASE)
            self.assertFalse(target.exists())
            self.assertEqual(client.calls,0)
            self.assertEqual(len(client.ledger),0)

    def test_single_atomic_intent_may_contain_two_legs_but_posts_once(self):
        obs=observation()
        client=FakeLedgerClient(obs)
        proposal=envelope()
        proposal['proposals'][0]['legs'].append({
            'condition':'market','token':'b','buy':True,
            'price':'.41','size':'5','expiresMs':BASE+250
        })
        with tempfile.TemporaryDirectory() as d:
            result=DurableVirtualPaperOrders(client).run(
                Path(d)/'out',obs,proposal,enable_virtual=True,at_ms=BASE)
            self.assertEqual(result['receiptCounts']['PAPER_SUBMITTED'],1)
            self.assertEqual(client.calls,1)
            self.assertEqual(len(client.ledger),1)
            self.assertEqual(len(next(iter(client.ledger.values()))['legs']),2)
            self.assertFalse(result['realOrdersEnabled'])

    def test_second_process_cannot_open_same_unfinished_outbox(self):
        obs=observation()
        client=FakeLedgerClient(obs)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out'
            out.mkdir()
            fd=os.open(str(out/'.lock'),os.O_RDWR|os.O_CREAT,0o600)
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    DurableVirtualPaperOrders(client).run(
                        out,obs,envelope(),enable_virtual=True,at_ms=BASE)
                self.assertFalse((out/'manifest.json').exists())
                self.assertEqual(client.calls,0)
            finally:
                fcntl.flock(fd,fcntl.LOCK_UN)
                os.close(fd)

    def test_malformed_server_receipt_is_never_recorded_as_success(self):
        obs=observation()
        class Malicious(FakeLedgerClient):
            def retry_identical(self,request):
                self.calls+=1
                return {'id':request['id'],'status':'LIVE_SUBMITTED',
                        'liveAllowed':True,'virtualOnly':False}
        client=Malicious(obs)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out'
            with self.assertRaisesRegex(ValueError,'Unsafe'):
                DurableVirtualPaperOrders(client).run(
                    out,obs,envelope(),enable_virtual=True,at_ms=BASE)
            self.assertEqual(list(out.glob('receipt-*.json')),[])

    def test_get_response_clock_may_advance_without_blocking_original_intent(self):
        from copy import deepcopy
        obs=observation(); client=FakeLedgerClient(obs)
        client.obs=deepcopy(obs); client.obs['generatedMs']=BASE+1
        client.obs['sequence']=2; client.obs['inputMs']=BASE+1
        with tempfile.TemporaryDirectory() as d:
            r=DurableVirtualPaperOrders(client).run(Path(d)/'out',obs,envelope(),enable_virtual=True,at_ms=BASE+1)
            self.assertEqual(r['receiptCounts']['PAPER_SUBMITTED'],1)
            self.assertEqual(next(iter(client.ledger.values()))['sequence'],1)
        client=FakeLedgerClient(obs); client.obs=deepcopy(obs); client.obs['generatedMs']=BASE+251
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'expired'):
                DurableVirtualPaperOrders(client).run(Path(d)/'out',obs,envelope(),enable_virtual=True,at_ms=BASE+251)
            self.assertEqual(client.calls,0)

if __name__=='__main__':
    unittest.main()
