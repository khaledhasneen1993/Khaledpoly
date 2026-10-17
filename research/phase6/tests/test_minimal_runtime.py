from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from research.phase6 import minimal_runtime as runtime

class MinimalRuntimeTest(unittest.TestCase):
    def test_loopback_paper_only_command_and_persistent_account(self):
        with tempfile.TemporaryDirectory() as root:
            jar=Path(root)/'executor-service/target/executor-service-0.6.0.jar';jar.parent.mkdir(parents=True);jar.touch()
            with patch.object(runtime.subprocess,'check_output',return_value='a'*40):
                cmd=runtime.command(root,Path(root)/'state',8080)
                self.assertIn('--server.address=127.0.0.1',cmd)
                self.assertIn('--hft.mode=PAPER',cmd)
                self.assertIn('--paper.closed-loop.enabled=true',cmd)
                self.assertIn('--executor.account.state-path='+str(Path(root)/'state/account.json'),cmd)
                with self.assertRaises(ValueError): runtime.command(root,root,80)
    def test_environment_requires_token_and_strips_venue_credentials(self):
        with self.assertRaises(ValueError): runtime.child_environment({})
        env=runtime.child_environment({'POLYBOT_EXECUTOR_TOKEN':'x'*32,'POLYMARKET_PRIVATE_KEY':'secret','HFT_POLYMARKET_KEY':'secret','PATH':'bin'})
        self.assertEqual(set(env),{'POLYBOT_EXECUTOR_TOKEN','PATH'})
    def test_health_checks_bound_response_and_fail_closed(self):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch.object(runtime,'urlopen',return_value=response):
            response.read.return_value=b'{"status":"UP"}';self.assertTrue(runtime.healthy(8080))
            response.read.return_value=b'x'*65537;self.assertFalse(runtime.healthy(8080))
            response.read.return_value=b'{"status":"DOWN"}';self.assertFalse(runtime.healthy(8080))
            response.read.return_value=b'[]';self.assertFalse(runtime.healthy(8080))
    def test_restart_budget_uses_identical_state_and_never_resets_risk(self):
        process=Mock();process.poll.return_value=1
        with tempfile.TemporaryDirectory() as state, patch.object(runtime,'child_environment',return_value={}),patch.object(runtime,'command',return_value=['paper','persistent-account']) as cmd,patch.object(runtime.subprocess,'Popen',return_value=process) as spawn,patch.object(runtime.time,'monotonic',side_effect=range(0,100,10)),patch.object(runtime.time,'sleep'):
            with self.assertRaisesRegex(RuntimeError,'budget exhausted'): runtime.run('.',state,max_restarts=1)
            self.assertEqual(cmd.call_count,1);self.assertEqual(spawn.call_count,2)
            self.assertEqual(spawn.call_args_list[0],spawn.call_args_list[1])
