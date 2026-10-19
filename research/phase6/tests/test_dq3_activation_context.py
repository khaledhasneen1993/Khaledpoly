import hashlib
import io
import json
import unittest
from research.phase6.dq3_activation_context import extract


class ActivationContextTest(unittest.TestCase):
    def source(self):
        events=[('DATASET_CONFIG',0,dict(format='normalized-public-v2',strategyIndependent=True)),
            ('RAW_MARKET',1000,dict(frameId=1,text='unchanged-original-public-text')),
            ('RESEARCH_FRAME',1001,dict(frameId=1,events=[dict(kind='BOOK',data=dict(token='a',sourceMs=1000,
                bids=[dict(price=str(i/100),size='840') for i in range(1,50)],asks=[dict(price='.51',size='100')]))])),
            ('RESEARCH_META',2000,dict(condition='m')),('RESEARCH_TICK',2200,{}),
            ('RESEARCH_TICK',2400,{}),('RUN_END',2700,dict(complete=True))]
        rows=[dict(schema=1,runId='r',seq=i,kind=k,arrivalMs=a,data=d) for i,(k,a,d) in enumerate(events,1)]
        raw=b''.join((json.dumps(r)+'\n').encode() for r in rows)
        spec=dict(startMs=0,endMs=2600,maxBookAgeMs=2000,sourceRows=len(rows),logicalTapeSha256=hashlib.sha256(raw).hexdigest(),
            states=[dict(originalSequence=i,submitMs=a) for i,a in [(4,2000),(5,2200),(6,2400)]])
        return raw,spec

    def test_full_depth_raw_and_all_original_inputs_preserved(self):
        raw,spec=self.source();r=extract(io.BytesIO(raw),spec)
        self.assertEqual(len(r['records']),4)
        first=r['records'][0];self.assertEqual(first['raw']['data']['text'],'unchanged-original-public-text')
        self.assertEqual(len(first['input']['data']['events'][0]['data']['bids']),49)
        self.assertFalse(r['actualCandidateAccountOrCancellationSimulated']);self.assertFalse(r['fillsInferred'])
        self.assertFalse(r['pnlInferred']);self.assertTrue(r['fullNormalizedDepthUnmodified'])

    def test_hash_chronology_frame_anchor_warmup_and_cap_fail_closed(self):
        raw,spec=self.source()
        for bad in [dict(spec,startMs=1),dict(spec,logicalTapeSha256='0'*64),dict(spec,sourceRows=8),
                    dict(spec,states=[dict(originalSequence=2,submitMs=1000)]*3)]:
            with self.assertRaises(ValueError):extract(io.BytesIO(raw),bad)
        with self.assertRaises(ValueError):extract(io.BytesIO(raw),spec,max_bytes=1)
        for broken in [raw[:-1],raw.replace(b'"frameId": 1',b'"frameId": 2',1),raw+raw.splitlines()[0]+b'\n']:
            with self.assertRaises(ValueError):extract(io.BytesIO(broken),dict(spec,logicalTapeSha256=hashlib.sha256(broken).hexdigest()))


if __name__=='__main__':unittest.main()
