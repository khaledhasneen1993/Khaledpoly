"""Censored own-order labels and probability/latency research must abstain on missing evidence."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase5.fill_research import evaluate_models
CUT=2000000000000

def label(i,start,basis='PAPER_MODEL',positive=True):
    result={'orderId':'o'+str(i),'marketId':'m'+str(i),'submittedMs':start,
            'featureObservedMs':start,'labelEndMs':start+6000,
            'provenance':basis,'features':{'spread':'.02','queue_ahead':'5',
              'inventory_imbalance':'0','source_age_ms':'50',
              'seconds_to_expiry':'60','volatility':'.1'},
            'fillMs':start+400 if positive else None,
            'secondLegMs':start+600 if positive else None,
            'markout':'-.005' if positive else None,
            'markoutObservedMs':start+5500 if positive else None}
    return result

class FillEvaluationTest(unittest.TestCase):
    def test_balanced_synthetic_labels_still_never_qualify_venue(self):
        rows=[label(i,CUT-12000-i*10000,positive=(i%2==0)) for i in range(6)]
        rows += [label(10+i,CUT+1000+i*10000,positive=(i%2==0)) for i in range(6)]
        report=evaluate_models(rows,CUT,min_train=4,min_holdout=4,min_class=2)
        self.assertEqual(report['sourceProvenance'],'PAPER_MODEL')
        self.assertEqual(report['targets']['fill']['status'],'RESEARCH_MODEL_UNQUALIFIED')
        self.assertEqual(report['targets']['fill']['trainingRows'],6)
        self.assertEqual(report['targets']['fill']['holdoutRows'],6)
        self.assertEqual(report['targets']['fill']['labelSummary']['positive'],6)
        self.assertIsNotNone(report['targets']['fill']['labelSummary']['observedFillLatencyP50Ms'])
        self.assertEqual(report['targets']['adverse_selection']['labelSummary']['censored'],6)
        self.assertFalse(report['calibratedVenueModelAvailable'])
        self.assertEqual(report['decision'],'NO_GO')

    def test_insufficient_censored_rows_not_negative_fills(self):
        row=label(1,CUT+1000,positive=False)
        row['labelEndMs']=row['submittedMs']+100
        output=evaluate_models([row],CUT,min_train=1,min_holdout=1,min_class=1)
        self.assertEqual(output['targets']['fill']['labelSummary']['censored'],1)
        self.assertEqual(output['targets']['fill']['labelSummary']['negative'],0)
        self.assertEqual(output['targets']['fill']['status'],'INSUFFICIENT_EVIDENCE')
        self.assertFalse(output['liveAllowed'])

    def test_mixed_and_duplicate_provenances_fail_closed(self):
        row=label(1,CUT+1000)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            evaluate_models([row,row],CUT)
        with self.assertRaisesRegex(ValueError,'Mixing PAPER'):
            evaluate_models([row,label(2,CUT+2000,basis='VENUE_EXECUTION')],CUT)

    def test_second_leg_needs_first_fill_and_causal_order(self):
        row=label(1,CUT+1000)
        row['fillMs']=None
        with self.assertRaisesRegex(ValueError,'Second leg requires'):
            evaluate_models([row],CUT)
        row=label(2,CUT+1000)
        row['featureObservedMs']=row['submittedMs']+1
        with self.assertRaisesRegex(ValueError,'Noncausal'):
            evaluate_models([row],CUT)

if __name__=='__main__':
    unittest.main()
