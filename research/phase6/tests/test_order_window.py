import hashlib
import io
import json
import unittest
from research.phase6.order_window import extract, related


class OrderWindowTest(unittest.TestCase):
    def tape(self):
        events = [('RESEARCH_META',0,{'condition':'m'}),
                  ('RESEARCH_FRAME',10,{'events':[{'kind':'BOOK','data':{'token':'a','sourceMs':9}},
                                                {'kind':'TRADE','data':{'token':'b','sourceMs':8}}]}),
                  ('RESEARCH_GAP',11,{'reason':'disconnect'}),
                  ('RESEARCH_META',30,{'condition':'m','observedMs':30}),
                  ('RUN_END',40,{'complete':True})]
        rows = [dict(schema=1,seq=i+1,runId='r',kind=k,arrivalMs=t,data=d) for i,(k,t,d) in enumerate(events)]
        return b''.join((json.dumps(r)+'\n').encode() for r in rows)

    def spec(self): return [dict(startMs=5,endMs=20,tokens=['a','b'],condition='m')]

    def test_frames_and_source_order_preserved_no_future_metadata(self):
        tape = self.tape(); result = extract(io.BytesIO(tape),self.spec(),hashlib.sha256(tape).hexdigest())
        window = result['windows'][0]
        self.assertEqual(window['precedingMetadata']['arrivalMs'],0)
        self.assertEqual([r['seq'] for r in window['rows']],[2,3])
        self.assertEqual([r['kind'] for r in window['rows'][0]['data']['events']],['BOOK','TRADE'])
        self.assertFalse(result['fillsInferred'])

    def test_hash_incomplete_and_cap_fail_closed(self):
        tape = self.tape(); digest = hashlib.sha256(tape).hexdigest()
        with self.assertRaises(ValueError): extract(io.BytesIO(tape),self.spec(),'0'*64)
        with self.assertRaises(ValueError): extract(io.BytesIO(tape),self.spec(),digest,limit=1)
        incomplete = b'\n'.join(tape.splitlines()[:-1])+b'\n'
        with self.assertRaises(ValueError): extract(io.BytesIO(incomplete),self.spec(),hashlib.sha256(incomplete).hexdigest())

    def test_only_relevant_scoped_gaps_and_raw_tokens(self):
        self.assertFalse(related('RESEARCH_GAP',{'tokens':['c']},{'a','b'},'m'))
        self.assertTrue(related('RESEARCH_GAP',{'tokens':['b']},{'a','b'},'m'))
        self.assertTrue(related('RAW_MARKET',{'text':'token-b'},{'a','b'},'m'))
