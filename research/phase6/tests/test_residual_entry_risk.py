import base64
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile
from research.phase6.residual_entry_risk import assess


class ResidualEntryRiskTest(unittest.TestCase):
    def test_disabled_is_behavior_preserving_and_recorded_entry_fails_enabled_bound(self):
        args=('5','.34','.64','2.5','.01')
        self.assertTrue(assess(*args)['allow'])
        candidate=assess(*args,enabled=True)
        self.assertFalse(candidate['allow'])
        self.assertEqual(Decimal(candidate['worstCaseUnpairedLoss']),Decimal('3.21'))

    def test_budget_and_cost_boundary_no_size_increase_or_relaxed_risk(self):
        self.assertTrue(assess('5','.49','.49','2.46','.01',enabled=True)['allow'])
        self.assertFalse(assess('5','.49','.49','2.45','.01',enabled=True)['allow'])
        self.assertFalse(assess('5','.49','.49','0','.01',enabled=True)['allow'])

    def test_invalid_inputs_fail_closed(self):
        for args in [('NaN','.3','.6','2.5','.01'),('5','.3','1','2.5','.01'),('0','.3','.6','2.5','.01'),('5','.3','.6','-1','.01')]:
            with self.assertRaises(ValueError):assess(*args,enabled=True)

    def test_original_account_archive_exposes_real_dust_loss_not_profit(self):
        root=Path('research/experiments/exit-window-replay-20261018/result')
        raw=base64.b64decode(b''.join((root/'artifact.zip.b64').read_bytes().split()),validate=True)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'0a7f87d7d0a4922392577cf557a816864c3d626c1ac271475aa73056d67636ad')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            expected={'baseline/report.json','candidate/report.json','baseline/audit.jsonl','candidate/audit.jsonl','comparison.json'}
            self.assertEqual(set(z.namelist()),expected)
            self.assertEqual(len(z.namelist()),5)
            self.assertLess(sum(x.file_size for x in z.infolist()),8000000)
            r=json.loads(z.read('candidate/report.json'));c=json.loads(z.read('comparison.json'))
            self.assertEqual(z.read('comparison.json'),(root/'comparison.original.json').read_bytes())
            self.assertTrue(all(r.get(k)==v for k,v in c['variants']['candidate'].items()))
            self.assertEqual(r['settlementExperiment']['consumedBindings'],14)
            self.assertEqual(r['settlementExperiment']['labelBindings'],14)
            executions=r['executions'];self.assertEqual(len(executions),2)
            sale_loss=(Decimal(str(executions[0]['price']))-Decimal(str(executions[1]['price'])))*Decimal(str(executions[1]['size']))
            residual_basis=(Decimal(str(executions[0]['size']))-Decimal(str(executions[1]['size'])))*Decimal(str(executions[0]['price']))
            total=sale_loss+residual_basis+Decimal(str(r['feesAndSettlementCosts']))
            self.assertEqual(total,Decimal('1.80'));self.assertEqual(Decimal(str(r['netRealizedPnl'])),-total)
            self.assertEqual(Decimal(str(r['cash'])),Decimal('500')-total)
            self.assertEqual(r['decisionReasons']['DUST_AWAIT_RESOLUTION'],557)
            self.assertEqual(r['residualExpiryWorstCaseNotional'],2)
            self.assertTrue(r['halted']);self.assertFalse(r['independentPaperQualificationAllowed'])
        proof=json.loads((root/'dust-diagnosis.json').read_text())
        self.assertEqual(proof['metadata']['data']['minSize'],5)
        resolutions=[x for x in proof['originalAuditEvents'] if x['kind']=='RESOLVED']
        self.assertEqual(len(resolutions),1)
        self.assertEqual(resolutions[0]['data']['payouts'][executions[0]['token']],0)
