"""Frozen generated-only indexed original execution; defaults remain unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
from research.phase6.atomic_guard_build import materialize as guard,SESSION
from research.phase6.full_runner_build import once

FREEZE=Path('research/phase6/indexed-execution-freeze.json')
RUNNER='polybot-core/src/main/java/com/polybot/hft/paper/NativeFullTapeReplay.java'


def render_session(text):
    text=once(text,'  private boolean researchRecoveredCheckpoint;', '''  private IndexedExecutionLabels indexedExecution;
  synchronized void enableIndexedResearch(IndexedExecutionLabels labels){
    if(inputSequence!=0||indexedExecution!=null||labels!=settlementLabels)
      throw new IllegalStateException("Fresh explicit indexed research session required");
    withResearchNoOrderWitness(w->{w.requireValid();labels.attach(this,matching);indexedExecution=labels;return null;});
  }
  private boolean researchRecoveredCheckpoint;''')
    text=once(text,'    } else if (Set.of("BOOK", "TRADE", "GAP", "TICK").contains(kind)) {', '''    } else if (Set.of("BOOK", "TRADE", "GAP", "TICK").contains(kind)) {
      IndexedExecutionLabels.Observation indexedObservation=null;
      if(indexedExecution!=null && kind.equals("TRADE")) {
        try{indexedObservation=indexedExecution.observe(replayRowSequence,replayEventIndex,at,data);data=indexedObservation.verifiedTrade();}
        catch(RuntimeException error){suspend();throw error;}
      }''')
    text=once(text,'        var binding=settlementLabels!=null && kind.equals("TRADE")', '''        if(indexedObservation!=null)apply(indexedExecution.advance(indexedObservation,!kind.equals("TRADE"),at));
        else {
        var binding=settlementLabels!=null && kind.equals("TRADE")''')
    text=once(text,'        apply(binding==null?matching.accept(kind,at,data):matching.acceptSettlement(at,data,binding));',
              '        apply(binding==null?matching.accept(kind,at,data):matching.acceptSettlement(at,data,binding));\n        }')
    text=once(text,'      r.put("settlementVolumeConservation",matching.settlementDiagnostics());', '''      r.put("settlementVolumeConservation",matching.settlementDiagnostics());
      if(indexedExecution!=null)r.put("settlementVolumeConservationScope","KNOWN_NONEXPIRED_COMPONENTS_ONLY_UNKNOWN_VENUE_QUANTITY_NOT_ZERO");''')
    return text


def render_runner(text):
    text=once(text,'public final class NativeFullTapeReplay {','public final class IndexedOriginalTapeReplay {')
    return once(text,'      if (candidate) session.enableFrozenResearchPolicies();', '''      if(pool instanceof IndexedExecutionLabels indexed)session.enableIndexedResearch(indexed);
      if (candidate) session.enableFrozenResearchPolicies();''')


def materialize(output):
    spec=json.loads(FREEZE.read_bytes())
    for path,sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed indexed execution dependency '+path)
    prefix=guard(output);root=Path(output)
    for path,render in [(SESSION,render_session),(RUNNER,render_runner)]:
        source=root/path
        if hashlib.sha256(source.read_bytes()).hexdigest()!=spec['prefixSourcesSha256'][path]:raise ValueError('Changed indexed prefix')
        raw=render(source.read_text()).encode()
        if hashlib.sha256(raw).hexdigest()!=spec['generatedSourcesSha256'][path]:raise ValueError('Changed frozen indexed rendering')
        target=source if path==SESSION else source.with_name('IndexedOriginalTapeReplay.java');target.write_bytes(raw)
    result=dict(scope='ISOLATED_INDEXED_ORIGINAL_DEVELOPMENT_EXECUTION_NOT_QUALIFICATION',
                defaultCoreFilesModified=0,identityAndAtomicWitnessIntegrated=True,
                unknownVenueQuantity='UNKNOWN_NOT_ZERO',completeAccountComparisonPerformed=False,
                independentPaperQualificationAllowed=False,liveAllowed=False,prefix=prefix)
    (root/'indexed-execution-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(materialize(a.output),indent=2))
