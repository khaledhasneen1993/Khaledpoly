import copy
import json
import unittest
from decimal import Decimal as D
from research.phase6.session_bridge_result import ROOT,verify


class SessionBridgeResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.args=[json.loads((ROOT/n).read_text(),parse_float=D) for n in ['default-before.json','default-after.json','bridge-proof.json','build-provenance.json']]

    def test_default_parity_and_canonical_ledger_bridge(self):
        self.assertTrue(verify(*self.args)['completeDefaultReportParity'])

    def test_fake_cash_inventory_or_uncancelled_orders_cannot_pass(self):
        for key,value in [('cash',D('500')),('openOrderCount',1),('halted',False)]:
            a=copy.deepcopy(self.args);a[2]['syntheticTerminalSessionReport'][key]=value
            with self.assertRaisesRegex(ValueError,'cash/inventory'):verify(*a)
        a=copy.deepcopy(self.args);a[2]['syntheticTerminalSessionReport']['settlementVolumeConservation']['allocatedQuantity']=6
        with self.assertRaisesRegex(ValueError,'cash/inventory'):verify(*a)

    def test_no_market_profit_or_qualification_scope_escalation(self):
        for key in ['marketNetPnlRecomputed','fullAccountStrategyComparisonPerformed','frozenQw0AndFeePositivePoliciesIntegrated','independentPaperQualificationAllowed','liveAllowed']:
            a=copy.deepcopy(self.args);a[2][key]=True
            with self.assertRaisesRegex(ValueError,'Synthetic-only'):verify(*a)

    def test_default_behavior_or_base_source_mutation_fails(self):
        a=copy.deepcopy(self.args);a[1]['cash']=D('500')
        with self.assertRaisesRegex(ValueError,'parity'):verify(*a)
        a=copy.deepcopy(self.args);a[3]['defaultCoreFilesModified']=1
        with self.assertRaisesRegex(ValueError,'build scope'):verify(*a)


if __name__=='__main__':unittest.main()
