import datetime as dt, importlib.util, json, pathlib, tempfile, unittest
spec=importlib.util.spec_from_file_location('experiment',pathlib.Path(__file__).parents[1]/'experiment.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
class ExperimentTest(unittest.TestCase):
 def test_cannot_freeze_retroactively(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):e.freeze(e.ROOT/'research-config.json','2020-01-01T00:00:00Z',pathlib.Path(d)/'freeze.json')
 def test_training_cannot_see_holdout(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'data.jsonl';p.write_text(json.dumps({'arrivalMs':1800000000000,'kind':'RESEARCH_TICK','data':{}})+'\n')
   with self.assertRaises(ValueError):e.calibrate(p,'2026-01-01T00:00:00Z')
 def test_missing_evidence_is_no_go_and_never_unlocks_live(self):
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);start=(dt.datetime.now(e.UTC)+dt.timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
   e.freeze(e.ROOT/'research-config.json',start.isoformat(),d/'freeze.json')
   for n in ['base','stress']:(d/(n+'.json')).write_text('{}')
   report=e.evaluate(d/'freeze.json',d/'base.json',d/'stress.json')
   self.assertEqual(report['decision'],'NO_GO');self.assertFalse(report['phase3Allowed']);self.assertFalse(report['liveAllowed']);self.assertGreater(len(report['failures']),10)
 def test_complete_synthetic_evidence_exercises_go_branch_but_never_live(self):
  # A gate unit fixture, NOT market evidence or a real evaluation result.
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d);start=(dt.datetime.now(e.UTC)+dt.timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
   f=e.freeze(e.ROOT/'research-config.json',start.isoformat(),d/'freeze.json')
   b=dict(replayMode='closed-loop',strategyIndependentDataset=True,recordingClosedCleanly=True,revision='1'*40,
    firstArrivalMs=int(start.timestamp()*1000),lastArrivalMs=int((start+dt.timedelta(days=7)).timestamp()*1000),
    windowStartMs=int(start.timestamp()*1000),windowEndMs=int((start+dt.timedelta(days=7)).timestamp()*1000),freezeSha256=e.digest(d/'freeze.json'),
    inputSha256='unit-fixture',configuration=f['configuration'],resolvedTradedMarkets=100,executions=[{'liquidity':'MAKER'}]*100,
    quantityPairCompletion=1,maxDrawdown=1,residualExpiryWorstCaseNotional=0,dataGaps=0,riskBreaches=0,maxInputGapMs=250,
    missingMarkObservations=0,markoutSamples={'1000':100,'5000':100,'30000':100},netRealizedPnl=1,holdings={},openOrderCount=0,pendingTakers=0)
   s=dict(b);s['configuration']=dict(b['configuration']);s['configuration'].update(activationMs=1000,cancelMs=1000,queueMultiplier='4',feeMultiplier='2',mergeCost='0.06',redemptionCost='0.06')
   (d/'b.json').write_text(json.dumps(b));(d/'s.json').write_text(json.dumps(s));r=e.evaluate(d/'freeze.json',d/'b.json',d/'s.json')
   self.assertEqual(r['failures'],[]);self.assertEqual(r['decision'],'GO_EXTENDED_PAPER');self.assertFalse(r['liveAllowed'])
   s['windowStartMs']-=1;(d/'s.json').write_text(json.dumps(s));self.assertFalse(e.evaluate(d/'freeze.json',d/'b.json',d/'s.json')['phase3Allowed'])
if __name__=='__main__':unittest.main()
