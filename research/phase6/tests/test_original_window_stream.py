import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.original_window_stream import extract_to,MAX_RETAINED_BYTES
from research.phase6.dq3_last_activation import extract
from research.phase6.tests import test_dq3_last_activation as fixtures
from research.phase6.queue_aware_post_gap_context import spec


class OriginalWindowStreamTest(unittest.TestCase):
    def test_stream_matches_every_old_record_and_full_depth(self):
        raw,s=fixtures.LastActivationTest().source();old=extract(io.BytesIO(raw),s)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'context.gz';seen=[];m=extract_to(io.BytesIO(raw),s,path,seen.append)
            with gzip.open(path,'rb') as f:body=f.read()
            records=[json.loads(line) for line in body.splitlines()]
            self.assertEqual(records,old['records']);self.assertEqual(records,seen)
            self.assertEqual(m['retainedLogicalSha256'],hashlib.sha256(body).hexdigest())
            self.assertEqual(m['retainedBytes'],len(body));self.assertTrue(m['complete'])
            self.assertEqual(len(records[0]['input']['data']['events'][0]['data']['bids']),49)

    def test_cap_or_changed_source_never_promotes_partial_evidence(self):
        raw,s=fixtures.LastActivationTest().source()
        for source,kw in [(raw,dict(max_bytes=1)),(raw[:-1],{}),(raw+raw.splitlines()[0]+b'\n',{})]:
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp)/'context.gz'
                with self.assertRaises(ValueError):extract_to(io.BytesIO(source),s,p,lambda r:None,**kw)
                self.assertFalse(p.exists());self.assertTrue(p.with_name('context.gz.partial').exists())

    def test_anchor_warmup_and_original_frame_binding_fail_closed(self):
        raw,s=fixtures.LastActivationTest().source()
        cases=[(raw,dict(s,startMs=1)),(raw,dict(s,sourceRows=8)),(raw,dict(s,states=[])),(raw.replace(b'"frameId": 1',b'"frameId": 2',1),s)]
        for data,bad in cases:
            with tempfile.TemporaryDirectory() as temp:
                p=Path(temp)/'context.gz'
                with self.assertRaises(ValueError):extract_to(io.BytesIO(data),bad,p,lambda r:None)
                self.assertFalse(p.exists())

    def test_frozen_market_window_unchanged_and_no_evidence_overwrite(self):
        self.assertEqual(spec()['startMs'],1792269758873);self.assertEqual(spec()['endMs'],1792269786123)
        self.assertEqual(MAX_RETAINED_BYTES,512*1024*1024)
        raw,s=fixtures.LastActivationTest().source()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'context.gz';extract_to(io.BytesIO(raw),s,p,lambda r:None)
            with self.assertRaisesRegex(ValueError,'overwrite'):extract_to(io.BytesIO(raw),s,p,lambda r:None)


if __name__=='__main__':unittest.main()
