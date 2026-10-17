"""Coordinated collector never turns a short/failed job into proof of capture."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase4.capture_supervisor import plan, commands

SHA='b'*40


class SupervisorTest(unittest.TestCase):
    def test_exact_full_utc_window_and_two_distinct_read_only_collectors(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'new-capture'
            p=plan(path,revision=SHA,at_ms=1800000123456,days=7)
            self.assertEqual(p['targetEndMs']-p['firstFullUtcMidnightMs'],
                             7*86400000)
            self.assertGreater(p['javaMaxRuntimeSeconds'],7*86400)
            c=commands(p)
            self.assertIn('research.phase4.recorder',c['cex'])
            self.assertIn('scripts/collect-paper-data.sh',c['polymarket'])
            self.assertEqual(c['polymarketEnv']['PAPER_FIVE_MINUTE'],'false')
            self.assertEqual(c['polymarketEnv']['PAPER_RECORD_DIRECTORY'],
                             str(path/'polymarket'))
            self.assertFalse(p['realOrdersEnabled'])
            self.assertEqual(p['decision'],'NO_GO')

    def test_invalid_source_pins_and_git_output_location_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'Invalid immutable'):
            plan('/tmp/elsewhere',revision='uncommitted')
        with self.assertRaisesRegex(ValueError,'outside'):
            plan(ROOT/'research'/'output'/'new',revision=SHA)
        with self.assertRaisesRegex(ValueError,'Invalid immutable'):
            plan('/tmp/elsewhere',revision=SHA,interval=0)
        with tempfile.TemporaryDirectory() as folder:
            p=plan(Path(folder)/'recording',revision=SHA)
            with self.assertRaisesRegex(ValueError,'override'):
                commands(p,java_binary='unknown-live-client')

if __name__=='__main__':
    unittest.main()
