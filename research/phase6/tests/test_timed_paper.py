import unittest
from unittest.mock import Mock,patch
from research.phase6.timed_paper import run,wait_until,read,checkpoint
import tempfile
from pathlib import Path
import json

class TimedPaperTest(unittest.TestCase):
    def test_checkpoint_replaces_state_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'experiment.json'
            checkpoint(path,{'status':'STARTING'})
            checkpoint(path,{'status':'RUNNING'})
            self.assertEqual(json.loads(path.read_text())['status'],'RUNNING')
            self.assertEqual(len(list(Path(directory).iterdir())),1)

    def test_bounds_reject_before_starting_process(self):
        for seconds in (0,7201,True):
            with self.assertRaises(ValueError):run('.', '/unused', seconds)
    def test_deadline_stops_wait_and_process_exit_fails(self):
        proc=Mock();proc.poll.return_value=None
        with patch('research.phase6.timed_paper.time.monotonic',side_effect=[1,1,3]):
            with patch('research.phase6.timed_paper.time.sleep') as sleep:
                wait_until(2,proc,lambda:False)
                self.assertEqual(sleep.call_count,1)
        proc.poll.return_value=1
        with patch('research.phase6.timed_paper.time.monotonic',return_value=1):
            with self.assertRaisesRegex(RuntimeError,'unexpectedly'):wait_until(2,proc,lambda:False)
    def test_interruption_does_not_extend_deadline(self):
        with patch('research.phase6.timed_paper.time.monotonic',return_value=1):
            proc=Mock();wait_until(2,proc,lambda:True);proc.poll.assert_not_called()
    def test_api_is_loopback_authenticated_and_bounded(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch('research.phase6.timed_paper.urlopen',return_value=response) as request:
            response.read.return_value=b'{"decision":"NO_GO"}'
            self.assertEqual(read(18084,'test-token','paper-metrics')['decision'],'NO_GO')
            self.assertEqual(request.call_args.args[0].full_url,'http://127.0.0.1:18084/api/polymarket/paper-metrics')
            self.assertEqual(request.call_args.args[0].get_header('X-polybot-token'),'test-token')
            response.read.return_value=b'[]'
            with self.assertRaises(ValueError):read(18084,'test-token','paper-metrics')
