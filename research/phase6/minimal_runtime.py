"""Foreground PAPER supervisor. Account/risk state survives every bounded restart."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.request import urlopen


def command(root, state, port):
    root=Path(root).resolve(); state=Path(state).resolve()
    if type(port) is not int or not 1024<=port<=65535: raise ValueError('Invalid loopback port')
    jar=root/'executor-service/target/executor-service-0.6.0.jar'
    if not jar.is_file(): raise ValueError('Verified PAPER jar is missing')
    return ['java','-jar',str(jar),'--server.address=127.0.0.1','--server.port='+str(port),
        '--hft.mode=PAPER','--hft.events.enabled=false','--hft.strategy.gabagool.enabled=false',
        '--executor.sim.enabled=true','--paper.closed-loop.enabled=true','--paper.phase3.enabled=true',
        '--paper.market-data.enabled=true','--hft.polymarket.market-ws-enabled=true',
        '--executor.account.state-path='+str(state/'account.json'),
        '--paper.closed-loop.config='+str(root/'research/phase2/research-config.json'),
        '--paper.record.directory='+str(root/'research/data/minimal'),
        '--paper.record.revision='+subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()]


def child_environment(source):
    token=source.get('POLYBOT_EXECUTOR_TOKEN','')
    if len(token)<24 or not token.strip(): raise ValueError('Strong POLYBOT_EXECUTOR_TOKEN required')
    return {k:v for k,v in source.items() if not k.startswith(('POLYMARKET_','HFT_POLYMARKET_'))}


def healthy(port):
    try:
        with urlopen('http://127.0.0.1:'+str(port)+'/actuator/health',timeout=2) as response:
            raw=response.read(65537)
        if len(raw)>65536: return False
        payload=json.loads(raw)
        return isinstance(payload,dict) and payload.get('status')=='UP'
    except (OSError,ValueError): return False


def stop(process):
    if process.poll() is not None: return
    try: os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError: return
    try: process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL); process.wait(timeout=5)


def run(root,state,port=8080,max_restarts=0):
    if type(max_restarts) is not int or not 0<=max_restarts<=5: raise ValueError('Restart budget must be 0..5')
    env=child_environment(os.environ); cmd=command(root,state,port)
    Path(state).mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=open(Path(state)/'supervisor.lock','a')
    import fcntl
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        lock.close(); raise
    interrupted=False; process=None; restarts=0
    def shutdown(*args):
        nonlocal interrupted
        interrupted=True
    previous={sig:signal.signal(sig,shutdown) for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        while not interrupted:
            process=subprocess.Popen(cmd,cwd=root,env=env,start_new_session=True)
            unhealthy=0; started=time.monotonic(); ready=False
            while process.poll() is None and not interrupted:
                ok=healthy(port)
                if ok:
                    if not ready: print('PAPER ready: http://127.0.0.1:'+str(port)+'/paper.html',flush=True)
                    ready=True; unhealthy=0
                elif time.monotonic()-started>60: unhealthy+=1
                if unhealthy>=3: break
                time.sleep(2)
            stop(process)
            if interrupted: return
            if restarts>=max_restarts: raise RuntimeError('PAPER process failed; restart budget exhausted. Inspect ledger and logs.')
            restarts+=1
            print('PAPER restart '+str(restarts)+'; preserving account, risk stop and unknown outcomes',flush=True)
            deadline=time.monotonic()+min(30,2**restarts)
            while not interrupted and time.monotonic()<deadline: time.sleep(.25)
    finally:
        if process is not None: stop(process)
        for sig,handler in previous.items(): signal.signal(sig,handler)
        lock.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--state',required=True);p.add_argument('--port',type=int,default=8080);p.add_argument('--max-restarts',type=int,default=0)
    a=p.parse_args();run(Path(a.root).resolve(),a.state,a.port,a.max_restarts)
if __name__=='__main__': main()
