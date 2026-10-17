#!/usr/bin/env python3
"""Exercise the FULL strategy on each captured public dataset; never promote a short smoke."""
import json,pathlib,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from research.phase3.polybot_sdk.tapes import recorded_tapes
root=pathlib.Path(sys.argv[1]);jar='executor-service/target/executor-service-0.6.0.jar'
for tape in recorded_tapes(root):
 reports={}
 for mode,flags in [('baseline',[]),('stress',['--stress']),('raw-baseline',['--raw'])]:
  out=tape.parent/('replay-'+mode)
  cmd=['java','-Dloader.main=com.polybot.hft.executor.replay.ClosedLoopMain','-cp',jar,'org.springframework.boot.loader.launch.PropertiesLauncher',str(tape),str(out),'research/phase2/research-config.json']
  cmd.extend(flags)
  subprocess.run(cmd,check=True)
  r=json.loads((out/'report.json').read_text())
  print(json.dumps({'mode':mode,'cash':r['cash'],'netRealizedPnl':r['netRealizedPnl'],'fills':len(r['executions']),'dataGaps':r['dataGaps'],'decision':r['decision']}))
  assert r['decision']=='NO_GO', 'A short smoke cannot authorize promotion'
  reports[mode]=r
 if reports['baseline'].get('frameAtomicity')=='recorded-frame-v1':
  for key,value in reports['baseline'].items():
   if key!='inputFormat':
    assert reports['raw-baseline'].get(key)==value, 'Raw/normalized report mismatch: '+key
  def audit(mode):
   return [json.loads(line) for line in (tape.parent/('replay-'+mode)/'audit.jsonl').read_text().splitlines() if line]
  assert audit('baseline')==audit('raw-baseline'), 'Raw/normalized action audit mismatch'
  print(json.dumps({'rawNormalizedParity':True,'scope':'all report fields except inputFormat, and full action audit'}))
