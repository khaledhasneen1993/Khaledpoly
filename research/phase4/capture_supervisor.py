"""Prospective external-host supervisor for existing PUBLIC collectors.

Launches the Java Polymarket read-only recorder and CEX public REST
recorder together; NEVER qualifies output by runtime alone. Fatal
failure of either stops the other. Required durable host is external.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from research.phase3.polybot_sdk.model import dumps, integer
from research.phase3.polybot_sdk.runtime import private_write
from research.phase4.recorder import current_clean_commit
from research.phase4.audit import DAY_MS

PROJECT=Path(__file__).resolve().parents[2]


def plan(root, *, revision, days=7, symbol='BTCUSDT', at_ms=None,
         interval=5, segment_seconds=900):
    if (not re.fullmatch(r'[0-9a-f]{40}',revision)
        or not re.fullmatch(r'[A-Z0-9]{3,20}USDT',symbol)
        or type(days) is not int or not 1<=days<=30
        or type(interval) is not int or not 1<=interval<=60
        or type(segment_seconds) is not int or not 5<=segment_seconds<=86400):
        raise ValueError('Invalid immutable capture plan')
    observed=integer(at_ms if at_ms is not None else time.time_ns()//1000000)
    if observed<0:
        raise ValueError('Invalid UTC wall clock')
    first_full=((observed+DAY_MS-1)//DAY_MS)*DAY_MS
    end=first_full+days*DAY_MS
    duration=(end-observed)//1000+180
    path=Path(root).resolve()
    if PROJECT==path or PROJECT in path.parents:
        raise ValueError('Use a persistent output location outside the Git checkout')
    return {'schema':1,'scope':'UNQUALIFIED_PUBLIC_CAPTURE_SUPERVISOR',
            'sourceRevision':revision,'startedAtMs':observed,
            'firstFullUtcMidnightMs':first_full,'targetEndMs':end,
            'targetFullUtcDays':days,'targetSymbol':symbol,
            'intervalSeconds':interval,'segmentSeconds':segment_seconds,
            'javaMaxRuntimeSeconds':duration,
            'root':str(path),'mode':'PUBLIC_RECORD_ONLY',
            'realOrdersEnabled':False,'liveAllowed':False,'decision':'NO_GO'}


def commands(p, java_binary='java'):
    path=Path(p['root'])
    if java_binary!='java':
        raise ValueError('Java binary override is disabled')
    java_env={
        'PAPER_RECORD_DIRECTORY':str(path/'polymarket'),
        'PAPER_RECORD_SECONDS':str(p['javaMaxRuntimeSeconds']),
        'PAPER_FIVE_MINUTE':'false'
    }
    cex=[sys.executable,'-m','research.phase4.recorder',
         '--root',str(path/'cex'),'--symbol',p['targetSymbol'],
         '--days',str(p['targetFullUtcDays']),
         '--segment-seconds',str(p['segmentSeconds']),
         '--interval',str(p['intervalSeconds'])]
    clob=['bash','scripts/collect-paper-data.sh']
    return {'cex':cex,'polymarket':clob,'polymarketEnv':java_env}


def _stop(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=10)


def run(root, *, days=7, symbol='BTCUSDT', interval=5, segment_seconds=900):
    revision=current_clean_commit()
    p=plan(root,revision=revision,days=days,symbol=symbol,
           interval=interval,segment_seconds=segment_seconds)
    folder=Path(p['root'])
    folder.mkdir(mode=0o700,parents=True,exist_ok=False)
    private_write(folder/'supervisor-plan.json',p)
    c=commands(p)
    java_env=os.environ.copy()
    java_env.update(c['polymarketEnv'])
    workers={}
    logs={}
    try:
        for name,cmd in [('polymarket',c['polymarket']),('cex',c['cex'])]:
            log=folder/(name+'.log')
            f=log.open('x',encoding='utf-8')
            os.chmod(log,0o600)
            logs[name]=f
            workers[name]=subprocess.Popen(
                cmd,cwd=PROJECT,env=java_env if name=='polymarket' else None,
                stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        while True:
            statuses={name:process.poll() for name,process in workers.items()}
            if any(v is not None for v in statuses.values()):
                break
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in workers.values():
            _stop(process)
        for logfile in logs.values():
            logfile.close()
    result={'schema':1,'scope':'EXTERNAL_PUBLIC_CAPTURE_SUPERVISOR_RESULT',
            'sourceRevision':revision,'finishedAtMs':int(time.time()*1000),
            'exitCodes':{name:proc.returncode for name,proc in workers.items()},
            'CEXAuditMustBeRunSeparately':True,
            'CLOBEventJournalAuditMustBeRunSeparately':True,
            'recordingIsNotQualification':True,
            'sevenDayMarketCaptureVerified':False,'decision':'NO_GO',
            'liveAllowed':False}
    private_write(folder/'supervisor-result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description='Linux 24/7 read-only CEX+Polymarket collector supervisor')
    parser.add_argument('--root',required=True,help='New empty persistent directory outside project')
    parser.add_argument('--days',type=int,default=7)
    parser.add_argument('--symbol',default='BTCUSDT')
    parser.add_argument('--interval',type=int,default=5)
    parser.add_argument('--segment-seconds',type=int,default=900)
    args=parser.parse_args()
    print(dumps(run(args.root,days=args.days,symbol=args.symbol,
                    interval=args.interval,segment_seconds=args.segment_seconds)))


if __name__=='__main__':
    main()
