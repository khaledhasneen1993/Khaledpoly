"""New isolated temporal witness. Old empty-order guard and defaults stay frozen."""
import argparse
import hashlib
import json
from pathlib import Path
from research.phase6.indexed_execution_build import materialize as indexed,SESSION
from research.phase6.atomic_guard_build import MATCHER
from research.phase6.full_runner_build import once

FREEZE=Path('research/phase6/preactivation-freeze.json')
LABELS='research/phase6/IndexedExecutionLabels.java'

MATCHER_METHOD='''
  record ResearchPendingBuy(String token,java.math.BigDecimal price,java.math.BigDecimal remaining) {}
  synchronized java.util.Map<String,ResearchPendingBuy> researchPreActivationBuys(long at,long source){
    if(at<now||source<0||source>at||orders.isEmpty())throw new IllegalStateException("No temporal pending-buy witness");
    var result=new java.util.HashMap<String,ResearchPendingBuy>();
    for(var order:orders.values()){
      if(order.active||!order.buy||order.activation<=at||order.cancel!=Long.MAX_VALUE||order.remaining.signum()<=0)
        throw new IllegalStateException("Active/due/cancel/sell order cannot use pending-buy witness");
      result.put(order.id,new ResearchPendingBuy(order.token,order.price,order.remaining));
    }
    return java.util.Map.copyOf(result);
  }
'''
SESSION_METHOD='''
  /** Narrow temporal witness: no live order yet; never changes activation or queue. */
  synchronized <T> T withResearchPreActivationWitness(long at,long source,java.util.function.Function<NoOrderWitness,T> action){
    java.util.Objects.requireNonNull(action);
    synchronized(ledger){synchronized(matching){synchronized(checkpoint){
      var state=ledger.snapshot();
      if(externalMode||researchRecoveredCheckpoint||failed||entryStopped||state.halted()||!pending.isEmpty()
          ||!unhedged.isEmpty()||!ledger.researchPersistenceHealthy()||!checkpoint.researchHealthy()
          ||ledger.availableCash().signum()<0
          ||state.holdings().values().stream().anyMatch(h->h.shares().signum()!=0||h.basis().signum()!=0))
        throw new IllegalStateException("Temporal witness requires healthy flat session");
      var waiting=matching.researchPreActivationBuys(at,source);
      var reserved=new java.util.HashSet<String>();
      for(var entry:state.orders().entrySet()){
        var o=entry.getValue();
        if(o.remaining().signum()==0&&java.util.Set.of("CANCELED","FILLED","REJECTED").contains(o.status()))continue;
        var match=waiting.get(entry.getKey());
        if(match==null||!o.buy()||!o.status().equals("OPEN")||o.filled().signum()!=0
            ||o.original().compareTo(o.remaining())!=0||!o.token().equals(match.token())
            ||o.price().compareTo(match.price())!=0||o.remaining().compareTo(match.remaining())!=0)
          throw new IllegalStateException("Temporal witness reservation differs from pending matcher order");
        reserved.add(entry.getKey());
      }
      if(!reserved.equals(waiting.keySet()))throw new IllegalStateException("Temporal witness missing reservation");
      var witness=new NoOrderWitness(this);
      try{return action.apply(witness);}finally{witness.active=false;}
    }}}
  }
  synchronized <T> T withResearchUnfillableWitness(long at,long source,java.util.function.Function<NoOrderWitness,T> action){
    synchronized(ledger){synchronized(matching){synchronized(checkpoint){
      if(matching.researchHasNoOrders())return withResearchNoOrderWitness(action);
      return withResearchPreActivationWitness(at,source,action);
    }}}
  }
'''


def render(path,text):
    if path==MATCHER:return once(text,'  synchronized boolean researchHasNoOrders()',MATCHER_METHOD+'\n  synchronized boolean researchHasNoOrders()')
    if path==SESSION:return once(text,'  private IndexedExecutionLabels indexedExecution;',SESSION_METHOD+'\n  private IndexedExecutionLabels indexedExecution;')
    if path==LABELS:
        text=once(text,'  private long knownApplied,knownExpired,unknownClock,unknownExpired;',
                  '  private long knownApplied,knownExpired,unknownClock,unknownExpired,preActivationClock;')
        text=once(text,'      return session.withResearchNoOrderWitness(witness->{',
                  '      return session.withResearchUnfillableWitness(at,observation.identity.source(),witness->{\n        boolean preActivation=!matcher.researchHasNoOrders();')
        text=once(text,'        unknownClock++;if(expired)unknownExpired++;',
                  '        unknownClock++;if(preActivation)preActivationClock++;if(expired)unknownExpired++;')
        return once(text,'    r.put("sourceIndex",index.report());',
                    '    r.put("temporalWitnessProfile","PRE_ACTIVATION0");r.put("unknownPreActivationClockObservations",preActivationClock);\n    r.put("sourceIndex",index.report());')
    raise ValueError('Unexpected temporal witness target')


def materialize(output):
    spec=json.loads(FREEZE.read_bytes())
    for p,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=sha:raise ValueError('Changed temporal experiment input '+p)
    provenance=indexed(output);root=Path(output)
    for path in (SESSION,MATCHER,LABELS):
        original=root/path if path!=LABELS else Path(path)
        if hashlib.sha256(original.read_bytes()).hexdigest()!=spec['prefixSourcesSha256'][path]:raise ValueError('Changed temporal prefix '+path)
        raw=render(path,original.read_text()).encode()
        if hashlib.sha256(raw).hexdigest()!=spec['generatedSourcesSha256'][path]:raise ValueError('Changed frozen temporal witness '+path)
        target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    result=dict(scope='GENERATED_PRE_ACTIVATION0_DEVELOPMENT_ONLY',defaultCoreFilesModified=0,
        activationQueueFeeRiskParametersChanged=False,oldEmptyOrderGuardUnchanged=True,
        independentPaperQualificationAllowed=False,liveAllowed=False,prefix=provenance)
    (root/'preactivation-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.output),indent=2))
