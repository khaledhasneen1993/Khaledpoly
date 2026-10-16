#!/usr/bin/env python3
"""Exercise the FULL strategy on each captured public dataset; never promote a short smoke."""
import json,pathlib,subprocess,sys
root=pathlib.Path(sys.argv[1]);jar='executor-service/target/executor-service-0.0.1-SNAPSHOT.jar'
for tape in root.glob('*/events.jsonl'):
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
