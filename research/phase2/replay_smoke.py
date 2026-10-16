#!/usr/bin/env python3
"""Exercise the FULL strategy on each captured public dataset; never promote a short smoke."""
import json,pathlib,subprocess,sys
root=pathlib.Path(sys.argv[1]);jar='executor-service/target/executor-service-0.0.1-SNAPSHOT.jar'
for tape in root.glob('*/events.jsonl'):
 for mode in ['baseline','stress']:
  out=tape.parent/('replay-'+mode)
  cmd=['java','-Dloader.main=com.polybot.hft.executor.replay.ClosedLoopMain','-cp',jar,'org.springframework.boot.loader.launch.PropertiesLauncher',str(tape),str(out),'research/phase2/research-config.json']
  if mode=='stress':cmd.append('--stress')
  subprocess.run(cmd,check=True)
  r=json.loads((out/'report.json').read_text())
  print(json.dumps({'mode':mode,'cash':r['cash'],'netRealizedPnl':r['netRealizedPnl'],'fills':len(r['executions']),'dataGaps':r['dataGaps'],'decision':r['decision']}))
  assert r['decision']=='NO_GO', 'A short smoke cannot authorize promotion'
