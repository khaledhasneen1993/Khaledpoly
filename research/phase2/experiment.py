#!/usr/bin/env python3
"""Freeze before holdout, inspect TRAIN-only latency, evaluate immutable baseline/stress evidence."""
import re
import argparse, datetime as dt, hashlib, json, pathlib, statistics
from decimal import Decimal as D
UTC=dt.timezone.utc
ROOT=pathlib.Path(__file__).resolve().parent

def read(p): return json.loads(pathlib.Path(p).read_text())
def digest(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for block in iter(lambda:f.read(65536),b''): h.update(block)
    return h.hexdigest()
def implementation_digest():
    repo=ROOT.parents[1]
    files=[]
    for module in ['polybot-core','executor-service','strategy-service']:
        files.extend((repo/module/'src/main/java').rglob('*.java'))
        files.append(repo/module/'pom.xml')
    files.extend([repo/'pom.xml',pathlib.Path(__file__).resolve()])
    files=sorted(files)
    h=hashlib.sha256()
    for p in files: h.update(str(p.relative_to(repo)).encode());h.update(p.read_bytes())
    return h.hexdigest()

def freeze(config, start, output):
    begin=dt.datetime.fromisoformat(start.replace('Z','+00:00'))
    if begin.tzinfo is None or begin.utcoffset()!=dt.timedelta(0) or begin.time()!=dt.time(): raise ValueError('Holdout starts at UTC midnight')
    now=dt.datetime.now(UTC)
    if begin<=now: raise ValueError('Freeze must precede holdout; cannot retroactively declare heldout data')
    cfg=read(config)
    if D(cfg['initialCash'])!=D('500'): raise ValueError('Registered experiment capital is 500; do not silently change criteria')
    result={'schema':1,'implementationSha256':implementation_digest(),'createdAt':now.isoformat(),'holdoutStart':begin.isoformat(),'holdoutEnd':(begin+dt.timedelta(days=7)).isoformat(),
            'configFileSha256':digest(config),'configuration':cfg,'acceptanceSha256':digest(ROOT/'acceptance.json'),'acceptance':read(ROOT/'acceptance.json')}
    with pathlib.Path(output).open('x') as f: json.dump(result,f,indent=2)
    return result

def calibrate(tape, split):
    cutoff=int(dt.datetime.fromisoformat(split.replace('Z','+00:00')).timestamp()*1000)
    lags=[];rtts=[];rows=0
    with pathlib.Path(tape).open() as f:
        for line in f:
            r=json.loads(line)
            if r['arrivalMs']>=cutoff: raise ValueError('Training input reaches holdout: refuse calibration')
            rows+=1
            if r['kind']=='CLOCK_SYNC': rtts.append(r['data']['rttMs'])
            if r['kind']=='RESEARCH_BOOK': lags.append(r['arrivalMs']-r['data']['sourceMs'])
            if r['kind']=='RESEARCH_FRAME':
                for event in r['data']['events']:
                    if event['kind']=='BOOK': lags.append(r['arrivalMs']-event['data']['sourceMs'])
    percentile=lambda xs: None if not xs else sorted(xs)[min(len(xs)-1,int(.95*(len(xs)-1)))]
    return {'trainingSha256':digest(tape),'trainingRows':rows,'sourceLagP95Ms':percentile(lags),'clockRttP95Ms':percentile(rtts),
            'conservativeActivationLowerBoundMs':max(250,percentile(rtts) or 0),
            'queueMultiplier':2,'queueNote':'L2 prints do not identify own FIFO rank. Do not fit optimistic queue credit or fill probabilities without independent queue labels.'}

def evaluate(frozen, baseline, stress):
    f=read(frozen);b=read(baseline);s=read(stress);criteria=f['acceptance'];fail=[]
    def require(ok, reason):
        if not ok: fail.append(reason)
    require(f.get('implementationSha256')==implementation_digest(),'Strategy implementation changed after freeze')
    require(f['acceptanceSha256']==digest(ROOT/'acceptance.json'),'Acceptance criteria changed after freeze')
    start=dt.datetime.fromisoformat(f['holdoutStart']);end=dt.datetime.fromisoformat(f['holdoutEnd'])
    require(dt.datetime.fromisoformat(f['createdAt'])<start,'Invalid freeze time')
    require(end-start>=dt.timedelta(days=criteria['minimumHeldoutDays']),'Holdout shorter than registered duration')
    require(b.get('inputSha256')==s.get('inputSha256') and bool(b.get('inputSha256')),'Baseline and stress must use identical observations')
    # Canonical numeric comparison is applied below.
    expected=dict(f['configuration']);expected.update(activationMs=1000,cancelMs=1000,queueMultiplier='4',feeMultiplier='2',mergeCost=str(D(expected['mergeCost'])+D('0.05')),redemptionCost=str(D(expected['redemptionCost'])+D('0.05')))
    # JSON numeric representations may differ; compare decimal-valued parameters numerically.
    def canonical(cfg): return {k:str(D(str(v)).normalize()) if isinstance(v,(int,float)) or isinstance(v,str) and v.replace('.','',1).isdigit() else v for k,v in cfg.items()}
    require(canonical(b.get('configuration',{}))==canonical(f['configuration']),'Baseline configuration differs from frozen configuration')
    require(canonical(s.get('configuration',{}))==canonical(expected),'Stress configuration differs from registered stress')
    for label,r in [('baseline',b),('stress',s)]:
        require(r.get('freezeSha256')==digest(frozen),label+': replay not bound to this preregistered split')
        require(r.get('windowStartMs')==int(start.timestamp()*1000) and r.get('windowEndMs')==int(end.timestamp()*1000),label+': performance includes observations outside the heldout window')
        require(r.get('replayMode')=='closed-loop',label+': action replay is not a strategy experiment')
        require(r.get('strategyIndependentDataset') is True,label+': independent collector provenance missing')
        require(r.get('frameAtomicity')=='recorded-frame-v1',label+': atomic frame provenance missing')
        require(r.get('decisionClock')=='recorded-inputs',label+': recorded decision clock missing')
        require(r.get('recordingClosedCleanly') is True,label+': incomplete recording')
        require(re.fullmatch(r'[0-9a-f]{40}',str(r.get('strategyRevision',''))) is not None,label+': replay strategy revision missing')
        require(re.fullmatch(r'[0-9a-f]{40}',str(r.get('revision',''))) is not None,label+': code provenance missing')
        require(r.get('firstArrivalMs',10**30)<=int(start.timestamp()*1000) and r.get('lastArrivalMs',-1)>=int(end.timestamp()*1000),label+': seven complete heldout UTC days missing')
        require(r.get('resolvedTradedMarkets',0)>=criteria['minimumResolvedMarkets'],label+': insufficient verified resolved markets')
        maker=sum(x.get('liquidity')=='MAKER' for x in r.get('executions',[]))
        require(maker>=criteria['minimumMakerFills'],label+': insufficient maker fills')
        q=r.get('quantityPairCompletion');require(q is not None and D(str(q))>=D(criteria['minimumQuantityPairCompletion']),label+': quantity completion below threshold or unknown')
        require(D(str(r.get('maxDrawdown','Infinity')))<=D(criteria['maximumDrawdownFraction'])*D(criteria['initialCash']),label+': drawdown exceeds limit')
        require(D(str(r.get('residualExpiryWorstCaseNotional','Infinity')))<=D(criteria['maximumResidualExpiryNotional']),label+': excessive expiry residual')
        require(r.get('maxInputGapMs',10**30)<=int(f['configuration']['maxBookAgeMs']),label+': input coverage has unexplained receive-time gaps')
        require(r.get('dataGaps',1)<=criteria['maximumDataGaps'],label+': data gaps')
        require(r.get('riskBreaches',1)<=criteria['maximumRiskBreaches'],label+': risk breaches')
        require(r.get('openOrderCount',1)==0 and r.get('pendingTakers',1)==0,label+': outstanding execution intentions remain')
        require(r.get('missingMarkObservations',1)==0,label+': inventory marks missing')
        require(all(r.get('markoutSamples',{}).get(str(h),0)>0 for h in [1000,5000,30000]),label+': markout evidence missing')
        require(D(str(r.get('netRealizedPnl','-Infinity')))>0,label+': net realized PnL is not positive')
        require(all(D(str(h['shares']))==0 for h in r.get('holdings',{}).values()),label+': unresolved or unliquidated inventory')
    return {'schema':1,'decision':'NO_GO' if fail else 'GO_EXTENDED_PAPER','phase3Allowed':not fail,'liveAllowed':False,'failures':fail,
            'baselineSha256':digest(baseline),'stressSha256':digest(stress),'freezeSha256':digest(frozen)}

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    f=sub.add_parser('freeze');f.add_argument('config');f.add_argument('utc_start');f.add_argument('output')
    c=sub.add_parser('calibrate');c.add_argument('training_jsonl');c.add_argument('holdout_start')
    e=sub.add_parser('evaluate');e.add_argument('freeze');e.add_argument('baseline');e.add_argument('stress');e.add_argument('output')
    a=p.parse_args()
    if a.command=='freeze': result=freeze(a.config,a.utc_start,a.output)
    elif a.command=='calibrate': result=calibrate(a.training_jsonl,a.holdout_start)
    else:
        result=evaluate(a.freeze,a.baseline,a.stress)
        with pathlib.Path(a.output).open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
