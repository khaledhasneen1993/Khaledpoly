import io
import json
import unittest
from research.phase6.opportunity_census import census


class OpportunityCensusTest(unittest.TestCase):
    def run_tape(self, gap=False, complete=True):
        events = [('RESEARCH_META', {'condition': 'm', 'first': 'a', 'second': 'b', 'tick': '.01',
                                    'minSize': '1', 'accepting': True, 'startMs': 0, 'endMs': 900000, 'observedMs': 0})]
        for token, bid in (('a', '.4'), ('b', '.55')):
            events.append(('RESEARCH_BOOK', {'token': token, 'sourceMs': 0, 'bids': [{'price': bid, 'size': '100'}],
                                             'asks': [{'price': '.8', 'size': '100'}]}))
        if gap: events.append(('RESEARCH_GAP', {'token': 'a', 'reason': 'test'}))
        events.append(('RESEARCH_TRADE', {'token': 'a', 'sourceMs': 10, 'side': 'SELL', 'price': '.4', 'size': '1000'}))
        if complete: events.append(('RUN_END', {'complete': True}))
        rows = [dict(schema=1, seq=i+1, runId='r', arrivalMs=10 if kind in ('RESEARCH_TRADE','RUN_END') else 0,
                     kind=kind, data=data) for i,(kind,data) in enumerate(events)]
        stream = io.BytesIO(b''.join((json.dumps(row)+'\n').encode() for row in rows))
        return census(stream, dict(maxBookAgeMs=2000, metadataMaxAgeMs=60000, orderShares='5', mergeCost='.01', minimumEdge='.01'))

    def test_quote_alignment_is_necessary_not_a_fill_or_profit(self):
        result = self.run_tape()
        self.assertEqual(result['policyCounts']['0'], {'NECESSARY_CONDITIONS_ONLY': 1})
        self.assertEqual(result['policyCounts']['1'], {'QUOTE_NOT_AT_PRINT': 1})
        self.assertFalse(result['fillsInferred']); self.assertFalse(result['pnlInferred'])
        self.assertEqual(result['decision'], 'NO_GO')

    def test_gap_blocks_census_and_missing_end_fails(self):
        self.assertEqual(self.run_tape(gap=True)['policyCounts']['0'], {'DEPTH_UNAVAILABLE': 1})
        with self.assertRaises(ValueError): self.run_tape(complete=False)
