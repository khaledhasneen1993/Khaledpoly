import base64
import copy
from decimal import Decimal
import io
import json
import unittest
import zipfile
from research.phase6.dq3_selected_gate import ROOT,analyze,verify_cancel


class SelectedGateTest(unittest.TestCase):
    def test_all11_precise_scoped_reasons_and_ack_before_first_print(self):
        r=analyze()
        self.assertEqual(r,json.loads((ROOT/'selected-gate.json').read_text()))
        self.assertEqual(len(r['results']),11)
        self.assertEqual(r['finalConditionalCancel']['cancelAckMs'],1792269786347)
        self.assertEqual(r['finalConditionalCancel']['millisecondsBeforeFirstPrint'],51)
        self.assertFalse(r['candidateAccountSimulated']);self.assertFalse(r['netPnlRecomputed'])

    def test_fake_early_cancel_and_entry_quantity_cannot_close_gate(self):
        with zipfile.ZipFile(io.BytesIO(base64.b64decode((ROOT/'last-cancel-result/artifact.zip.b64').read_bytes()))) as z:
            r=json.loads(z.read('cancel-report.json'),parse_float=Decimal)
        for field,value in [('restingQuantity',Decimal('.5')),('cancelDueMs',1792269786096)]:
            bad=copy.deepcopy(r);bad[field]=value
            with self.assertRaises(ValueError):verify_cancel(bad)
        bad=copy.deepcopy(r);bad['targetDiagnostic']['terminalMs']=1792269786398
        with self.assertRaises(ValueError):verify_cancel(bad)


if __name__=='__main__':unittest.main()
