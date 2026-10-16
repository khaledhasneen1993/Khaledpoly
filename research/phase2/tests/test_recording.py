import importlib.util
import json
import pathlib
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('recording_inspector', pathlib.Path(__file__).parents[1] / 'inspect_recording.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecordingTest(unittest.TestCase):
    def tape(self, root, rows):
        path = pathlib.Path(root) / 'events.jsonl'
        path.write_text(''.join(json.dumps(dict(schema=1, runId='a', seq=i+1, **r))+'\n'
                                for i, r in enumerate(rows)))
        return path

    def test_measured_staleness_is_attributed_without_claiming_wire_latency(self):
        with tempfile.TemporaryDirectory() as root:
            p = self.tape(root, [
                dict(arrivalMs=3000, kind='RAW_MARKET', data=dict(callbackReceivedMs=2999, text=json.dumps(dict(timestamp='1000')))),
                dict(arrivalMs=3001, kind='RESEARCH_GAP', data=dict(reason='stale_source', callbackSourceAgeMs=1999, processingAgeMs=2)),
                dict(arrivalMs=3002, kind='RESEARCH_GAP', data=dict(reason='stale_source', callbackSourceAgeMs=2500, processingAgeMs=1)),
                dict(arrivalMs=3003, kind='RUN_END', data=dict(complete=True))])
            report = MODULE.inspect(p)
            self.assertEqual(report['gapReasons'], {'stale_source': 2})
            self.assertEqual(report['staleStages'], {'crossed_limit_during_processing': 1, 'already_stale_at_callback': 1})
            self.assertEqual(report['callbackToJournal']['maxMs'], 1)
            self.assertTrue(report['recordingClosedCleanly'])
            self.assertEqual(report['decision'], 'NO_GO')

    def test_atomic_frame_provenance_and_nested_quality_are_checked(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [dict(arrivalMs=1000, kind='DATASET_CONFIG', data=dict(format='normalized-public-v2')),
                    dict(arrivalMs=1001, kind='RAW_MARKET', data=dict(frameId=1, text='{}')),
                    dict(arrivalMs=1002, kind='RESEARCH_FRAME', data=dict(frameId=1, events=[
                        dict(kind='BOOK', data=dict(sourceMs=1000)),
                        dict(kind='GAP', data=dict(reason='invalid_depth'))])),
                    dict(arrivalMs=1003, kind='RUN_END', data=dict(complete=True))]
            report = MODULE.inspect(self.tape(root, rows))
            self.assertEqual(report['frameAtomicity'], 'recorded-frame-v1')
            self.assertEqual(report['normalizedEvents'], dict(BOOK=1, GAP=1))
            self.assertEqual(report['gapReasons'], dict(invalid_depth=1))
            self.assertEqual(report['normalizedSourceAge']['maxMs'], 2)
            rows[2]['data']['frameId'] = 2
            with self.assertRaisesRegex(ValueError, 'matching raw'):
                MODULE.inspect(self.tape(root, rows))
            with self.assertRaisesRegex(ValueError, 'without completed frame'):
                MODULE.inspect(self.tape(root, rows[:2] + rows[3:]))

    def test_incomplete_capture_stays_incomplete(self):
        with tempfile.TemporaryDirectory() as root:
            report = MODULE.inspect(self.tape(root, [dict(arrivalMs=1000, kind='RESEARCH_TICK', data={})]))
            self.assertFalse(report['recordingClosedCleanly'])
            self.assertEqual(report['staleStages'], {})

    def test_receive_clock_regression_and_trailing_events_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'regressed'):
                MODULE.inspect(self.tape(root, [dict(arrivalMs=1000, kind='X', data={}), dict(arrivalMs=999, kind='X', data={})]))
            with self.assertRaisesRegex(ValueError, 'after RUN_END'):
                MODULE.inspect(self.tape(root, [dict(arrivalMs=1000, kind='RUN_END', data=dict(complete=True)), dict(arrivalMs=1001, kind='X', data={})]))
