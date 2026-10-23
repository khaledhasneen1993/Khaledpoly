import hashlib
from pathlib import Path
import unittest
from research.phase6.full_runner_build import SOURCE,SOURCE_SHA,once,render

class FullRunnerBuildTest(unittest.TestCase):
    def test_original_hash_and_default_class_preserved(self):
        source=SOURCE.read_text();self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),SOURCE_SHA)
        made=render(source);self.assertIn('class NativeFullTapeReplay',made)
        self.assertIn('pool!=null ? new ResearchSession',made)
        self.assertIn('else if (settlementLabels==null) session.accept(input, at, data);',made)

    def test_modified_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'source changed'):render(SOURCE.read_text()+' ')

    def test_ambiguous_transform_rejected(self):
        for source in ('x','xx'):
            with self.assertRaises(ValueError):once(source,'xx' if source=='x' else 'x','new')

    def test_parser_body_unchanged_except_dispatch_and_failure_tracking(self):
        source=SOURCE.read_text();made=render(source)
        original=source.split('        if (kind.equals("DATASET_CONFIG")) {',1)[1].split('          if (settlementLabels==null)',1)[0]
        self.assertIn(original,made)
        # Sequence, original RAW/frame parser, all RESEARCH_ kinds and clock handling identical.
        for marker in ('row.path("schema").asInt() != 1','row.path("seq").asLong() != ++seq',
                       'session.acceptReplay(input,at,data,seq)','pool.requireConsumed();',
                       'NativeReplaySupport.failure(out,mapper,currentRow'):
            self.assertIn(marker,made)

    def test_no_unknown_skip_or_synthetic_rewrite(self):
        made=render(SOURCE.read_text())
        self.assertNotIn('catch(IllegalArgumentException',made)
        self.assertNotIn('Unknown original observation',made)
        self.assertIn('session.suspend();',made)
        self.assertIn('throw failure;',made)

if __name__=='__main__':unittest.main()
