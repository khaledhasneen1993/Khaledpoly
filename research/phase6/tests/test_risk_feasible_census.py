import copy
import json
from pathlib import Path
import unittest
from research.phase6.risk_feasible_census import BASE, ORDERS, recover_quantity, screen, attach_historical_qb0


class RiskFeasibleCensusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path('research/phase2/research-config.json').read_text())
        cls.fresh = json.loads((BASE/'fresh.json').read_text())
        cls.original = json.loads((BASE/'original.json').read_text())

    def test_all_examples_and_unchanged_risk_filter(self):
        for data, total, legacy, join in [(self.original,84,1,1), (self.fresh,590,4,13)]:
            result = screen(data, self.config)
            self.assertEqual(result['completeNecessaryExamples'], total)
            self.assertEqual(result['recoveredCensusQuantityCounts'], {'5':total})
            allowed = result['riskAdmissibleExamples']
            self.assertEqual(sum(r['improvementTicks']==1 for r in allowed), legacy)
            self.assertEqual(sum(r['improvementTicks']==0 for r in allowed), join)
            self.assertFalse(result['actualEntryDecisionStateReconstructed'])

    def test_fresh_legacy_candidates_have_no_matching_active_order(self):
        orders = json.loads(ORDERS.read_text())['makerExecutionDiagnostics']
        result = screen(self.fresh, self.config, orders)
        rows = [r for r in result['riskAdmissibleExamples'] if r['improvementTicks']==1]
        self.assertEqual([r['at'] for r in rows], [1792269711484,1792269712920,1792269724135,1792269724142])
        self.assertTrue(all(not r['actualLegacyGuardMatchingActiveOrderIds'] for r in rows))
        self.assertLess(rows[0]['sourceMs'], orders[0]['submittedMs'])
        self.assertTrue(all(r['at']>orders[0]['terminalMs'] for r in rows[1:]))

    def test_missing_or_changed_evidence_fails_closed(self):
        bad = copy.deepcopy(self.fresh); bad['examplesTruncated'] = True
        with self.assertRaisesRegex(ValueError, 'complete'):
            screen(bad, self.config)
        bad = copy.deepcopy(self.fresh); bad['examples'].pop()
        with self.assertRaisesRegex(ValueError, 'counts mismatch'):
            screen(bad, self.config)
        row = dict(self.fresh['examples'][0], netEdgeUpperBound='999')
        with self.assertRaisesRegex(ValueError, 'absent/ambiguous'):
            recover_quantity(row, self.config)
        config = dict(self.config, mergeCost='0')
        with self.assertRaisesRegex(ValueError, 'positive cost'):
            recover_quantity(self.fresh['examples'][0], config)

    def test_historical_qb0_had_no_matching_orders_not_a_new_guard_replay(self):
        for name, census in [('original', self.original), ('fresh', self.fresh)]:
            result = screen(census, self.config)
            report = json.loads(Path('research/experiments/quote-qb0-20261018/'+name+'-candidate-report.json').read_text())
            attach_historical_qb0(result, report, self.config)
            rows = [r for r in result['riskAdmissibleExamples'] if r['improvementTicks']==0]
            self.assertTrue(all(not r['historicalUnguardedQb0MatchingSubmittedOrderIds'] for r in rows))
            self.assertTrue(all(not r['historicalUnguardedQb0MatchingActiveOrderIds'] for r in rows))
            report['configuration']['makerImprovementTicks'] = 1
            with self.assertRaisesRegex(ValueError, 'configuration'):
                attach_historical_qb0(result, report, self.config)


if __name__ == '__main__':
    unittest.main()
