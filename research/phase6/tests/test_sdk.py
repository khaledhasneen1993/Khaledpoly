"""Installable phase 6 declarative SDK can't run scripts or bypass central review."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'research'/'phase3'/'tests'))
from test_research import BASE, fixture
from research.phase6.sdk import preview, compile_declarative


def spec():
    return {'schema':1,'version':'1.0','strategyId':'independent-paper',
            'proposals':[{'id':'probe','edge':'.03',
                          'legs':[{'condition':'market','token':'a','buy':True,
                                   'price':'.41','size':'5','expiresMs':BASE+250}]}]}


class DeclarativeSdkTest(unittest.TestCase):
    def test_compiles_account_scoped_declarative_hypothesis_with_no_order_path(self):
        original=spec()
        report=preview(fixture(),original,at_ms=BASE)
        self.assertEqual(report['contractVersion'],'1.0')
        self.assertEqual(report['review']['admittedResearchCandidates'],1)
        self.assertFalse(report['callerStrategyExecutedInProcess'])
        self.assertEqual(report['paperOrdersSubmitted'],0)
        self.assertEqual(report['venueOrdersSubmitted'],0)
        self.assertFalse(report['liveAllowed'])
        self.assertNotIn('accountId', original)

    def test_rejects_code_exec_bypass_and_bad_version(self):
        unsafe=spec()
        unsafe['exec']='import os'
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            compile_declarative(fixture(),unsafe,at_ms=BASE)
        unsafe=spec()
        unsafe['proposals'][0]['legs'][0]['privateKey']='unsafe'
        with self.assertRaisesRegex(ValueError,'Undeclared'):
            preview(fixture(),unsafe,at_ms=BASE)
        unsafe=spec()
        unsafe['version']='2.0'
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            compile_declarative(fixture(),unsafe,at_ms=BASE)

    def test_rejects_bypassed_risk_and_source_staleness(self):
        bad=spec()
        bad['proposals'][0]['legs'][0]['price']='.61'
        result=preview(fixture(),bad,at_ms=BASE)
        self.assertEqual(result['review']['admittedResearchCandidates'],0)
        with self.assertRaisesRegex(ValueError,'Stale'):
            preview(fixture(),spec(),at_ms=BASE+10000)

if __name__=='__main__':
    unittest.main()
