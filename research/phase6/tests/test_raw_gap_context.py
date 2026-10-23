import hashlib
import io
import json
import unittest
from research.phase6.raw_gap_context import extract


class RawGapContextTest(unittest.TestCase):
    def tape(self, anchor_kind='GAP'):
        text='[{"event_type":"price_change","asset_id":"a","price_changes":[]}]'
        events=[('DATASET_CONFIG',0,{'format':'normalized-public-v2'}),
            ('RAW_MARKET',5,{'frameId':1,'text':text}),
            ('RESEARCH_FRAME',6,{'frameId':1,'events':[
                {'kind':'BOOK','data':{'token':'a','sourceMs':5,
                    'bids':[{'price':str(i/10),'size':'2'} for i in range(1,5)],
                    'asks':[{'price':'.6','size':'3'}]}},
                {'kind':anchor_kind,'data':{'token':'b','sourceMs':5,'reason':'invalid_depth'}}]}),
            ('RESEARCH_GAP',7,{'token':'c'}),('RUN_END',10,{'complete':True})]
        return b''.join((json.dumps(dict(schema=1,runId='r',seq=i,kind=k,arrivalMs=at,data=d))+'\n').encode()
            for i,(k,at,d) in enumerate(events,1)),text

    def spec(self, raw):
        return dict(tokens=['a','b'],startMs=1,endMs=9,logicalTapeSha256=hashlib.sha256(raw).hexdigest(),
            anchors=[dict(seq=3,eventIndex=1,at=6,sourceMs=5,reason='invalid_depth')])

    def test_raw_preserved_frame_bound_and_projection_explicit(self):
        raw,text=self.tape();r=extract(io.BytesIO(raw),self.spec(raw))
        self.assertEqual(len(r['frames']),1);self.assertEqual(r['frames'][0]['raw']['data']['text'],text)
        events=r['frames'][0]['normalized']['data']['events']
        self.assertEqual(events[1]['originalEventIndex'],1)
        self.assertEqual(len(events[0]['data']['bids']),3)
        self.assertEqual(events[0]['data']['bids'][0]['price'],'0.4')
        self.assertEqual(r['standaloneGaps'],[])
        self.assertFalse(r['pnlInferred']);self.assertFalse(r['fillsInferred'])
        self.assertTrue(r['stateBeforeWindowNotReconstructed'])

    def test_anchor_hash_cap_and_incomplete_tape_fail_closed(self):
        raw,_=self.tape();spec=self.spec(raw)
        for changed in [dict(spec,logicalTapeSha256='0'*64),dict(spec,endMs=5),dict(spec,endMs=40000)]:
            with self.assertRaises(ValueError):extract(io.BytesIO(raw),changed)
        with self.assertRaises(ValueError):extract(io.BytesIO(raw),spec,max_bytes=1)
        with self.assertRaises(ValueError):extract(io.BytesIO(raw[:-1]),spec)
        bad,_=self.tape('TRADE')
        with self.assertRaises(ValueError):extract(io.BytesIO(bad),self.spec(bad))

    def test_frame_mismatch_and_events_after_end_fail_closed(self):
        raw,_=self.tape()
        bad=raw.replace(b'"frameId": 1',b'"frameId": 2',1)
        with self.assertRaises(ValueError):extract(io.BytesIO(bad),self.spec(bad))
        with self.assertRaises(ValueError):extract(io.BytesIO(raw+raw.splitlines()[0]+b'\n'),self.spec(raw))


if __name__=='__main__':unittest.main()
