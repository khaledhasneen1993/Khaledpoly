import copy
import hashlib
import json
from pathlib import Path
import unittest
from research.phase6.full_runner_diagnosis import first_missing,verify_failure

class FullRunnerDiagnosisTest(unittest.TestCase):
    def test_frozen_original_first_missing_identity(self):
        r=first_missing();self.assertEqual((r['seq'],r['eventIndex']), (97,0))
        self.assertEqual(r['transactionHash'],'0x12251c3fc5cc98f770892d16a115904cec18f729ffb7f15d2f8558beeea196fc')

    def fixture(self):
        expected=first_missing();raw=json.dumps({'transaction_hash':expected['transactionHash']})
        expected['publicTradeIdSha256']=hashlib.sha256(raw.encode()).hexdigest()
        cfg=json.loads(Path('research/phase2/research-config.json').read_text())
        labels=dict(bindings=642,actualComponents=1516,consumedBindings=0,failed=True,aggregateFallbackAllowed=False,
            lastAttemptedOriginalObservation={**{k:expected[k] for k in ('seq','eventIndex','at')},'observation':{
                **{k:expected[k] for k in ('token','side','sourceMs','price','size')},'tradeId':raw}})
        p=dict(scope='INCOMPLETE_ORIGINAL_TAPE_FAIL_CLOSED_DIAGNOSTIC_NOT_FINANCIAL_RESULT',candidateFrozenPoliciesEnabled=True,decision='NO_GO',
            row=dict(seq=expected['seq'],kind='RESEARCH_FRAME',arrivalMs=expected['at']),labels=labels,
            errors=['IllegalArgumentException: Fail-closed pool resolution','IllegalArgumentException: Unknown original observation; incomplete pool is not zero'],
            sessionAfterSuspension=dict(halted=True,openOrderCount=0,frozenQw0AndFeePositivePoliciesIntegrated=True,settlementExperiment=labels,configuration=cfg),
            ledgerAfterSuspension=dict(halted=True))
        p.update({k:False for k in ('fullOriginalTapeCoverageProven','completeAccountComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed')})
        return p,expected,cfg

    def test_identity_and_nonfinancial_scope(self):
        p,e,c=self.fixture();self.assertFalse(verify_failure(p,e,True,c)['marketNetPnlRecomputed'])
        p['row']['seq']+=1
        with self.assertRaisesRegex(ValueError,'identity'):verify_failure(p,e,True,c)

    def test_safety_and_no_financial_promotion(self):
        p,e,c=self.fixture()
        for field in ('completeAccountComparisonPerformed','marketNetPnlRecomputed','liveAllowed'):
            bad=copy.deepcopy(p);bad[field]=True
            with self.assertRaisesRegex(ValueError,'financial'):verify_failure(bad,e,True,c)
        bad=copy.deepcopy(p);bad['sessionAfterSuspension']['openOrderCount']=1
        with self.assertRaisesRegex(ValueError,'Fail-closed'):verify_failure(bad,e,True,c)

    def test_real_errors_or_fee_risk_changes_cannot_pass(self):
        p,e,c=self.fixture();p['errors']=['OutOfMemoryError']
        with self.assertRaisesRegex(ValueError,'Unexpected'):verify_failure(p,e,True,c)
        p,e,c=self.fixture();p=copy.deepcopy(p);p['sessionAfterSuspension']['configuration']['queueMultiplier']='1'
        with self.assertRaisesRegex(ValueError,'Risk/fee/queue'):verify_failure(p,e,True,c)

if __name__=='__main__':unittest.main()
