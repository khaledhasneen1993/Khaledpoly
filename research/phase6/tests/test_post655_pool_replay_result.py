import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from research.phase6.post655_pool_replay_result import verify


class Post655PoolReplayResultTest(unittest.TestCase):
    def test_retained_exact657_result(self):
        result=verify();self.assertEqual(result['modelFills'],0);self.assertFalse(result['completeAccountComparisonPerformed'])
        self.assertEqual([result['nextReceiptTargets'][p]['seq'] for p in ('candidate','baseline')],[9662,83208])

    def test_mutated_summary_rejected(self):
        source=Path('research/experiments/post655-pool-replay-20261023/ci-artifact.zip')
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'bad.zip'
            with zipfile.ZipFile(source) as zin,zipfile.ZipFile(target,'w') as zout:
                for name in zin.namelist():
                    raw=zin.read(name)
                    if name=='development/summary.json':
                        value=json.loads(raw);value['completeAccountComparisonPerformed']=True;raw=json.dumps(value).encode()
                    zout.writestr(name,raw)
            with self.assertRaises(ValueError):verify(target)


if __name__=='__main__':unittest.main()
