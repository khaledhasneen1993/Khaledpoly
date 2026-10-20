"""Separately frozen generated SOURCE_LAG0 witness. No original/default edits."""
import argparse
import hashlib
import json
from pathlib import Path
from research.phase6.preactivation_build import materialize as prefix,SESSION,MATCHER,LABELS,SESSION_METHOD
from research.phase6.full_runner_build import once

FREEZE=Path('research/phase6/source-lag-guard-freeze.json')
MATCHER_METHOD='''
  synchronized boolean researchHasActiveOrders(){return orders.values().stream().anyMatch(o->o.active);}
  synchronized java.util.Map<String,ResearchPendingBuy> researchSourceLagBuys(long at,long source){
    if(at<now||source<0||source>at||orders.isEmpty())throw new IllegalStateException("No source-lag buy witness");
    var result=new java.util.HashMap<String,ResearchPendingBuy>();
    for(var order:orders.values()){
      if(!order.buy||order.cancel!=Long.MAX_VALUE||order.remaining.signum()<=0
          ||order.active&&(order.activated<0||source>order.activated))
        throw new IllegalStateException("Eligible/invalid/cancel/sell order cannot use source-lag witness");
      result.put(order.id,new ResearchPendingBuy(order.token,order.price,order.remaining));
    }
    return java.util.Map.copyOf(result);
  }
'''
# Exact unchanged OPEN reservation/flat/persistence/four-monitor checks, but a NEW predicate/method.
SOURCE_METHOD=SESSION_METHOD.split('  synchronized <T> T withResearchUnfillableWitness')[0]
SOURCE_METHOD=SOURCE_METHOD.replace('Narrow temporal witness: no live order yet; never changes activation or queue.',
    'Source-lag witness: every active order checks its OWN ACTUAL activated timestamp.')
SOURCE_METHOD=SOURCE_METHOD.replace('withResearchPreActivationWitness','withResearchSourceLagWitness')
SOURCE_METHOD=SOURCE_METHOD.replace('matching.researchPreActivationBuys','matching.researchSourceLagBuys')
SOURCE_METHOD=SOURCE_METHOD.replace('if(externalMode||','if(at<now||externalMode||')
SOURCE_METHOD+='''
  synchronized <T> T withResearchSourceLagUnfillableWitness(long at,long source,java.util.function.Function<NoOrderWitness,T> action){
    synchronized(ledger){synchronized(matching){synchronized(checkpoint){
      if(matching.researchHasNoOrders())return withResearchNoOrderWitness(action);
      return withResearchSourceLagWitness(at,source,action);
    }}}
  }
'''


def render(path,text):
    if path==MATCHER:return once(text,'  synchronized boolean researchHasNoOrders()',MATCHER_METHOD+'\n  synchronized boolean researchHasNoOrders()')
    if path==SESSION:return once(text,'  private IndexedExecutionLabels indexedExecution;',SOURCE_METHOD+'\n  private IndexedExecutionLabels indexedExecution;')
    if path==LABELS:
        text=once(text,'unknownExpired,preActivationClock;','unknownExpired,preActivationClock,sourceLagClock,sourceLagActiveClock;')
        text=once(text,'session.withResearchUnfillableWitness(at,observation.identity.source(),witness->{','session.withResearchSourceLagUnfillableWitness(at,observation.identity.source(),witness->{')
        text=once(text,'boolean preActivation=!matcher.researchHasNoOrders();','boolean sourceLag=!matcher.researchHasNoOrders(),active=matcher.researchHasActiveOrders();')
        text=once(text,'unknownClock++;if(preActivation)preActivationClock++;if(expired)unknownExpired++;','unknownClock++;if(sourceLag)sourceLagClock++;if(sourceLag&&active)sourceLagActiveClock++;if(expired)unknownExpired++;')
        text=once(text,'r.put("temporalWitnessProfile","PRE_ACTIVATION0");','r.put("temporalWitnessProfile","SOURCE_LAG0");r.put("unknownSourceLagClockObservations",sourceLagClock);r.put("unknownSourceLagActiveClockObservations",sourceLagActiveClock);')
        return text
    raise ValueError('Unexpected source-lag target')


def materialize(output):
    spec=json.loads(FREEZE.read_bytes())
    for path,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed source-lag guard dependency '+path)
    from research.phase6.source_lag_ci_result import load
    load()  # Mandatory preserved Java21 mathematical proof, NOT itself runtime authorization.
    provenance=prefix(output);root=Path(output)
    for path in (SESSION,MATCHER,LABELS):
        target=root/path;raw=target.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=spec['prefixSourcesSha256'][path]:raise ValueError('Changed source-lag prefix '+path)
        raw=render(path,raw.decode()).encode()
        if hashlib.sha256(raw).hexdigest()!=spec['generatedSourcesSha256'][path]:raise ValueError('Changed frozen source-lag guard '+path)
        target.write_bytes(raw)
    result=dict(scope='GENERATED_SOURCE_LAG0_DEVELOPMENT_NOT_QUALIFICATION',defaultCoreFilesModified=0,oldWitnessMethodsUnchanged=True,
        activationQueueFeeRiskParametersChanged=False,independentPaperQualificationAllowed=False,liveAllowed=False,prefix=provenance)
    (root/'source-lag-guard-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.output),indent=2))
