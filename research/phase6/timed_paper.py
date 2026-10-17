"""One bounded, disposable PAPER experiment. Never restart or reset risk to manufacture activity."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import time
from urllib.request import Request,urlopen
from research.phase6.minimal_runtime import command, child_environment, stop
from research.phase3.polybot_sdk.runtime import private_write


def checkpoint(path, data):
    path=Path(path)
    temp=path.with_name(path.name+'.tmp-'+secrets.token_hex(8))
    try:
        private_write(temp,data)
        os.replace(temp,path)
        fd=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        temp.unlink(missing_ok=True)


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(port, token, resource):
    req=Request('http://127.0.0.1:'+str(port)+'/api/polymarket/'+resource,
                headers={'X-Polybot-Token':token})
    with urlopen(req,timeout=3) as response:
        raw=response.read(16*1024*1024+1)
    if len(raw)>16*1024*1024: raise ValueError('Oversized PAPER response')
    value=json.loads(raw)
    if not isinstance(value,dict): raise ValueError('Invalid PAPER response')
    return value


def wait_until(deadline, process, interrupted):
    while time.monotonic()<deadline and not interrupted():
        if process.poll() is not None: raise RuntimeError('PAPER process exited unexpectedly')
        time.sleep(min(1,max(0,deadline-time.monotonic())))


def run(root,output,seconds=7200,port=18084):
    if type(seconds) is not int or not 1<=seconds<=7200: raise ValueError('Duration must be 1..7200 seconds')
    root=Path(root).resolve();output=Path(output).resolve()
    output.mkdir(parents=True,mode=0o700,exist_ok=False)
    token=secrets.token_urlsafe(32)
    env=child_environment(dict(os.environ,POLYBOT_EXECUTOR_TOKEN=token))
    cmd=command(root,output/'state',port)
    cmd=[x for x in cmd if not x.startswith('--paper.record.directory=')]
    cmd+=['--paper.record.directory='+str(output/'ingestor'),
          '--paper.phase3.execution.enabled=false','--paper.alerts.slack-webhook=',
          '--paper.alerts.telegram-token=','--paper.alerts.telegram-chat=']
    manifest={'scope':'BOUNDED_PUBLIC_DATA_VIRTUAL_PAPER_EXPERIMENT','requestedSeconds':seconds,
              'strategy':'CENTRAL_CLOSED_LOOP_COMPLETE_SET','mode':'PAPER',
              'revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
              'scheduledAtUtc':utc(),'status':'STARTING','decision':'NO_GO','liveAllowed':False,
              'autoRestart':False,'rebatesAssumed':0,'sampleIntervalSeconds':30}
    checkpoint(output/'experiment.json',manifest)
    interrupted=False;server=None;failure=None;last=None;samples=0;started=None
    def halt(*args):
        nonlocal interrupted
        interrupted=True
    previous={sig:signal.signal(sig,halt) for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        with (output/'executor.log').open('x') as log, (output/'metrics.jsonl').open('x') as metrics:
            server=subprocess.Popen(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            started=time.monotonic();deadline=started+seconds
            manifest.update(status='RUNNING',startedAtUtc=utc())
            checkpoint(output/'experiment.json',manifest)
            print('PAPER_EXPERIMENT_STARTED '+manifest['startedAtUtc']+' durationSeconds='+str(seconds),flush=True)
            failures=0
            while time.monotonic()<deadline and not interrupted:
                if server.poll() is not None: raise RuntimeError('PAPER process exited unexpectedly')
                try:
                    last=read(port,token,'paper-metrics')
                    if last.get('decision')!='NO_GO': raise RuntimeError('Unexpected PAPER safety contract')
                    sample={'observedAtUtc':utc(),'elapsedSeconds':round(time.monotonic()-started,3),'metrics':last}
                    metrics.write(json.dumps(sample,separators=(',',':'))+'\n');metrics.flush();os.fsync(metrics.fileno());samples+=1
                    checkpoint(output/'latest-metrics.json',sample)
                    # Small progress logs, while the full evidence stays in the artifact.
                    print(json.dumps({'elapsedSeconds':sample['elapsedSeconds'],'fills':last.get('fills'),
                        'cash':last.get('cash'),'pnl':last.get('netRealizedPnl'),'gaps':last.get('dataGaps'),
                        'halted':last.get('halted'),'activeMarkets':len(last.get('activeMarkets',[]))}),flush=True)
                    failures=0
                except (OSError,ValueError):
                    failures=0 if last is None and time.monotonic()-started<60 else failures+1
                    if failures>=4: raise RuntimeError('PAPER API unavailable for consecutive samples')
                wait_until(min(deadline,time.monotonic()+(1 if last is None else 30)),server,lambda:interrupted)
            if interrupted: raise RuntimeError('Experiment interrupted before requested duration')
            try:
                last=read(port,token,'paper-metrics');private_write(output/'final-metrics.json',last)
                private_write(output/'final-ledger.json',read(port,token,'paper-ledger'))
            except (OSError,ValueError) as error:
                raise RuntimeError('Final PAPER state could not be read') from error
    except Exception as error:
        failure=type(error).__name__+': '+str(error)
    finally:
        if server is not None: stop(server)
        elapsed=0 if started is None else time.monotonic()-started
        manifest.update(endedAtUtc=utc(),elapsedSeconds=round(elapsed,3),samples=samples,
                        status='FAILED' if failure else 'COMPLETED',failure=failure,
                        completedRequestedDuration=failure is None and elapsed>=seconds,
                        metricsReflectLastSuccessfulObservation=True)
        checkpoint(output/'experiment.json',manifest)
        for sig,handler in previous.items(): signal.signal(sig,handler)
    if failure: raise RuntimeError(failure)
    from research.phase2.inspect_recording import inspect
    try:
        tapes=list((output/'ingestor').glob('*/events.jsonl'))
        if len(tapes)!=1: raise RuntimeError('Expected one complete experiment journal')
        inspection=inspect(tapes[0]);private_write(output/'capture-inspection.json',inspection)
        if not inspection['recordingClosedCleanly']: raise RuntimeError('PAPER journal did not close cleanly')
    except Exception as error:
        manifest.update(status='FAILED',failure='Capture inspection failed: '+type(error).__name__)
        checkpoint(output/'experiment.json',manifest)
        raise
    print('PAPER_EXPERIMENT_COMPLETED '+manifest['endedAtUtc'],flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--output',required=True)
    p.add_argument('--seconds',type=int,default=7200)
    a=p.parse_args();run(a.root,a.output,a.seconds)
if __name__=='__main__':main()
