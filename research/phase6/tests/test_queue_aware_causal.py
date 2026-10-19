from collections import Counter
import copy
import json
import unittest
from research.phase6.queue_aware_causal import QROOT,selection_and_bindings,validate_terminal
from research.phase6.queue_aware_cached_traffic import cached_evidence,actual_priced_volume


class QueueAwareCausalTest(unittest.TestCase):
    def test_complete_generic_buy_sell_manifest_exact_original_bindings(self):
        spec,m=selection_and_bindings()
        self.assertEqual(m,json.loads((QROOT/'causal-bindings.json').read_text()))
        self.assertEqual((m['state']['quotes'][0]['price'],m['state']['quotes'][1]['price']),('0.48','0.4'))
        self.assertEqual(spec['endMs']-spec['startMs'],12571)
        self.assertEqual(len(m['bindings']),39)
        self.assertEqual(Counter(b['sample']['side'] for b in m['bindings']),dict(BUY=37,SELL=2))
        identities=[p['identity'] for b in m['bindings'] for p in b['parts']]
        self.assertEqual(len(identities),len(set(identities)))
        for b in m['bindings']:
            self.assertEqual(b['sample']['transaction_hash'],b['transactionHash'])
            self.assertGreaterEqual(b['sourceMs'],m['state']['activationDueMs'])
            self.assertLess(b['at'],m['state']['terminalMs'])
            for p in b['parts']:self.assertTrue(0<p['collateralRaw']<p['sharesRaw'])
        self.assertFalse(m['netPnlRecomputed']);self.assertTrue(m['restingRiskCancellationOmitted'])

    def test_missing_cached_receipt_fails_not_partial_zero(self):
        _,m=selection_and_bindings();cache=cached_evidence();del cache[m['bindings'][0]['transactionHash']]
        with self.assertRaisesRegex(ValueError,'Missing/duplicate'):selection_and_bindings(cache)

    def test_original_terminal_gap_must_match_pair_and_exact_time(self):
        spec,m=selection_and_bindings();at=m['state']['terminalMs'];token=m['state']['quotes'][1]['token']
        c=dict(records=[dict(input=dict(arrivalMs=at,kind='RESEARCH_FRAME',data=dict(events=[
            dict(kind='GAP',data=dict(reason='invalid_depth',token=token))])))])
        validate_terminal(c,spec)
        for changed in [dict(token='unrelated',reason='invalid_depth'),dict(token=token,reason='another')]:
            bad=copy.deepcopy(c);bad['records'][0]['input']['data']['events'][0]['data']=changed
            with self.assertRaises(ValueError):validate_terminal(bad,spec)


if __name__=='__main__':unittest.main()
