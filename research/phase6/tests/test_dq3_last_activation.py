import io
import unittest
from research.phase6.dq3_last_activation import extract
from research.phase6.tests import test_dq3_activation_context as fixtures


class LastActivationTest(unittest.TestCase):
    def source(self):
        raw,spec=fixtures.ActivationContextTest().source()
        spec['states']=spec['states'][:1];spec['endMs']=2100
        return raw,spec

    def test_full_depth_and_exact_tail_hash_not_optimistic_truncation(self):
        raw,spec=self.source();r=extract(io.BytesIO(raw),spec)
        self.assertEqual(len(r['records']),2)
        self.assertEqual(len(r['records'][0]['input']['data']['events'][0]['data']['bids']),49)
        self.assertTrue(r['tailIdentityBoundToPreviouslyValidatedCompleteSourceSha256'])
        self.assertFalse(r['fillsInferred']);self.assertFalse(r['pnlInferred'])
        # Although the tail is not repeatedly JSON-decoded, any change is rejected
        # against the previously validated COMPLETE original recording hash.
        changed=raw.replace(b'"arrivalMs": 2400',b'"arrivalMs": 2399')
        with self.assertRaises(ValueError):extract(io.BytesIO(changed),spec)

    def test_missing_anchor_warmup_terminal_frame_and_cap_fail_closed(self):
        raw,spec=self.source()
        for bad in [dict(spec,startMs=1),dict(spec,sourceRows=8),dict(spec,states=[]),
                    dict(spec,states=[dict(originalSequence=4,submitMs=2001)])]:
            with self.assertRaises(ValueError):extract(io.BytesIO(raw),bad)
        with self.assertRaises(ValueError):extract(io.BytesIO(raw),spec,max_bytes=1)
        for changed in [raw[:-1],raw.replace(b'"frameId": 1',b'"frameId": 2',1),raw+raw.splitlines()[0]+b'\n']:
            with self.assertRaises(ValueError):extract(io.BytesIO(changed),spec)


if __name__=='__main__':unittest.main()
