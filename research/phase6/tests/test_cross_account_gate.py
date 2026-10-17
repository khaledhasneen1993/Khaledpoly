"""Multi-account research segregation never reserves/executes/transfers funds."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'research'/'phase3'/'tests'))
from test_research import fixture, BASE
from research.phase3.polybot_sdk.accounts import AccountRegistry
from research.phase6.cross_account_gate import CrossAccountPaperGate


class IsolatedAccountGateTest(unittest.TestCase):
    def registry(self,folder,roles=None):
        r=roles or ['read','research']
        return AccountRegistry([
          {'alias':'one','origin':'http://127.0.0.1:18081','stateDirectory':str(Path(folder)/'one'),'roles':r},
          {'alias':'two','origin':'http://127.0.0.1:18082','stateDirectory':str(Path(folder)/'two'),'roles':['read','research']}
        ])
    def observation(self,account):
        snap=fixture()
        snap['account']['id']=account
        snap['sessionId']='session-'+account
        return snap

    def test_two_independent_accounts_are_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.registry(d)
            r.accept('one',self.observation('acct-one'),BASE)
            r.accept('two',self.observation('acct-two'),BASE)
            g=CrossAccountPaperGate(r,{'one':'200','two':'200'},'300','200')
            report=g.inspect(BASE)
            self.assertTrue(report['reconciliationComplete'])
            self.assertTrue(report['mayStudyPaperProposals'])
            self.assertFalse(report['mayReserveOrSubmit'])
            self.assertFalse(report['capitalTransfersEnabled'])
            self.assertEqual(report['combinedExposureUsd'],'0')

    def test_missing_and_stale_accounts_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.registry(d)
            r.accept('one',self.observation('acct-one'),BASE)
            g=CrossAccountPaperGate(r,{'one':'200','two':'200'},'300','200')
            report=g.inspect(BASE)
            self.assertIn('MISSING_ISOLATED_ACCOUNTS',report['issues'])
            self.assertFalse(report['mayStudyPaperProposals'])
            r.accept('two',self.observation('acct-two'),BASE)
            report=g.inspect(BASE+2001)
            self.assertIn('INCOMPLETE_OR_STALE_VALUATION',report['issues'])

    def test_group_concentration_is_joint_across_accounts(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.registry(d)
            for alias in ('one','two'):
                snap=self.observation('acct-'+alias)
                snap['account']['holdings']={'a':{'shares':'100','basis':'90'}}
                r.accept(alias,snap,BASE)
            g=CrossAccountPaperGate(r,{'one':'150','two':'150'},'250','120')
            report=g.inspect(BASE)
            self.assertIn('CORRELATED_SETTLEMENT_GROUP_CAP_EXCEEDED',report['issues'])
            self.assertEqual(report['settlementGroupExposureUsd']['market'],'180')
            self.assertFalse(report['mayReserveOrSubmit'])

    def test_read_only_account_cannot_research(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.registry(d,roles=['read'])
            r.accept('one',self.observation('acct-one'),BASE)
            r.accept('two',self.observation('acct-two'),BASE)
            report=CrossAccountPaperGate(r,{'one':'200','two':'200'},'300','200').inspect(BASE)
            self.assertIn('MISSING_RESEARCH_PERMISSION',report['issues'])

    def test_policy_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.registry(d)
            with self.assertRaisesRegex(ValueError,'aliases'):
                CrossAccountPaperGate(r,{'one':'200'},'500','200').inspect(BASE)


if __name__=='__main__':
    unittest.main()
