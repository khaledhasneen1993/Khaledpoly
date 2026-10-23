import base64
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile


class ResidualRiskResultTest(unittest.TestCase):
    def test_original_account_control_and_zero_fill_no_go(self):
        root=Path('research/experiments/residual-entry-risk-20261018/result')
        raw=base64.b64decode(b''.join((root/'artifact.zip.b64').read_bytes().split()),validate=True)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'680a934c5e0d38d57cbd85a725052e0771f3a1fcfae7a3958a07a37d405d4bf7')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertEqual(set(z.namelist()),{'control/report.json','control/audit.jsonl','candidate/report.json','candidate/audit.jsonl','comparison.json'})
            self.assertEqual(len(z.namelist()),5);self.assertLess(sum(x.file_size for x in z.infolist()),8000000)
            self.assertEqual(z.read('comparison.json'),(root/'comparison.original.json').read_bytes())
            comparison=json.loads(z.read('comparison.json'))
            for mode in ('control','candidate'):
                report=json.loads(z.read(mode+'/report.json'))
                self.assertTrue(all(report.get(k)==v for k,v in comparison['variants'][mode].items()))
                self.assertEqual(report['settlementExperiment']['consumedBindings'],14)
                self.assertEqual(report['settlementExperiment']['labelBindings'],14)
            control=comparison['variants']['control'];candidate=comparison['variants']['candidate']
            self.assertEqual(Decimal(str(control['netRealizedPnl'])),Decimal('-1.8'))
            self.assertEqual(candidate['submittedOrders'],2);self.assertEqual(candidate['fills'],0)
            self.assertEqual(candidate['netRealizedPnl'],0);self.assertEqual(candidate['cash'],500)
            self.assertIsNone(candidate['quantityPairCompletion'])  # Undefined is not a fabricated success ratio.
            self.assertEqual(candidate['decisionReasons']['ENTRY_RESIDUAL_LOSS_BUDGET'],31)
            self.assertFalse(comparison['independentPaperQualificationAllowed'])
            self.assertEqual(comparison['decision'],'NO_GO')
        proof=json.loads((root/'only-pair-diagnostic.json').read_text())
        self.assertEqual(len(proof['makerExecutionDiagnostics']),2)
        for order in proof['makerExecutionDiagnostics']:
            self.assertEqual(order['activeMs'],254)
            self.assertEqual(order['terminalReason'],'DATA_GAP:invalid_depth')
            self.assertEqual(order['eligiblePrintVolume'],0)
        self.assertEqual(proof['makerExecutionDiagnostics'][0]['terminalMs'],1792269711983)
