import copy
import unittest
from research.phase6.queue_aware_post_gap_context import spec,summarize


class PostGapContextTest(unittest.TestCase):
    def test_window_derived_from_unchanged_risk_clock_not_outcome(self):
        s=spec();self.assertEqual(s['endMs'],1792269786123);self.assertLess(s['endMs']-s['startMs'],30000)
        self.assertEqual(s['unchangedUnhedgedDeadlineMs'],1792269784123)

    def source(self):
        s=spec();g=s['firstGapMs'];b=lambda token:dict(kind='BOOK',data=dict(token=token,sourceMs=g+1,bids=[dict(price='.4',size='5')],asks=[dict(price='.6',size='5')]))
        row=lambda seq,at,events:dict(input=dict(seq=seq,arrivalMs=at,kind='RESEARCH_FRAME',data=dict(events=events)))
        return dict(spec=s,records=[row(260656,g,[dict(kind='GAP',data=dict(token='a',reason='invalid_depth'))]),row(260657,g+1,[b('a')]),row(260658,g+2,[]),row(260659,g+3,[b('b')])])

    def test_both_books_required_after_gap_empty_frame_not_callback(self):
        c=self.source();r=summarize(c,{'a','b'});self.assertEqual(r['firstFreshBothBookCallback']['seq'],260659)
        self.assertEqual(r['receiptRequests'],0);self.assertFalse(r['netPnlRecomputed'])
        c['records'].pop();self.assertIsNone(summarize(c,{'a','b'})['firstFreshBothBookCallback'])

    def test_missing_anchor_and_regressing_book_rejected_or_unknown(self):
        c=self.source();c['records'][0]['input']['seq']=1
        with self.assertRaisesRegex(ValueError,'anchor absent'):summarize(c,{'a','b'})
        c=self.source();c['records'][-1]['input']['data']['events'][0]['data']['sourceMs']=0
        self.assertIsNone(summarize(c,{'a','b'})['firstFreshBothBookCallback'])


if __name__=='__main__':unittest.main()
