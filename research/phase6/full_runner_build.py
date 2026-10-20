"""Exact source-derived offline runner; no original core or input filtering edits."""
import argparse
import hashlib
import json
from pathlib import Path
from research.phase6.strategy_profile_build import materialize as strategy

SOURCE=Path('polybot-core/src/main/java/com/polybot/hft/paper/ClosedLoopReplay.java')
SOURCE_SHA='046d30999a763d2735fa114562dae66c9bfd2e1f7bcbfac0953094938b3b466f'

def once(text, old, new):
    if text.count(old)!=1: raise ValueError('Runner source anchor is not unique: '+old[:80])
    return text.replace(old,new,1)

def render(source):
    if hashlib.sha256(source.encode()).hexdigest()!=SOURCE_SHA: raise ValueError('Original replay source changed')
    text=once(source,'public final class ClosedLoopReplay {','public final class NativeFullTapeReplay {')
    # Existing public/default parser paths remain intact. Only the deepest internal call gains
    # explicit offline labels/policy options; no timers/frames/metadata/actions are rewritten.
    text=once(text,'settlementLabels,residualEntryRiskGuard,null);','settlementLabels,residualEntryRiskGuard,null,null,false);')
    text=once(text,'false,labels,true,witness);','false,labels,true,witness,null,false);')
    text=once(text,'boolean residualEntryRiskGuard,EntryDecisionWitness witness) throws Exception {',
        'boolean residualEntryRiskGuard,EntryDecisionWitness witness,OfflineSessionLabels pool,boolean candidate) throws Exception {')
    text=once(text,'            new ResearchSession(\n                ledger,',
        '''            pool!=null ? new ResearchSession(ledger,config,mapper,out.resolve("session.json"),
                (kind,data)->audit.add(Map.of("kind",kind,"at",clock.millis(),"data",data)),
                false,"STRICT-ORIGINAL-TAPE",pool,false,OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0) : new ResearchSession(
                ledger,''')
    text=once(text,'      if (witness!=null) session.enableDecisionWitness(witness);',
        '''      if (candidate) session.enableFrozenResearchPolicies();
      if (witness!=null) session.enableDecisionWitness(witness);''')
    text=once(text,'      String line;\n      while', '      JsonNode currentRow=null;\n      try {\n      String line;\n      while')
    text=once(text,'        JsonNode row = mapper.readTree(line);','        JsonNode row = mapper.readTree(line);\n        currentRow=row;')
    text=once(text,'          if (settlementLabels==null) session.accept(input, at, data);',
        '          if (pool!=null) session.acceptReplay(input,at,data,seq);\n          else if (settlementLabels==null) session.accept(input, at, data);')
    text=once(text,'      if (pendingFrameId != -1)\n        throw new IllegalArgumentException("Raw observation without completed frame");',
        '''      if (pendingFrameId != -1)
        throw new IllegalArgumentException("Raw observation without completed frame");
      if (pool!=null) pool.requireConsumed();
      } catch(Exception failure) {
        session.suspend();
        NativeReplaySupport.failure(out,mapper,currentRow,session.report(),ledger.snapshot(),audit,pool,candidate,failure);
        throw failure;
      }''')
    text=once(text,'      result.put("decision", "NO_GO");', '''      result.put("decision", "NO_GO");
      if (pool!=null) {
        result.put("replayMode","strict-original-tape-partial-pool-development-only");
        result.put("strategyIndependentDataset",false);
        result.put("fullOriginalTapeCoverageProven",false);
        result.put("fullAccountReplayAuthorized",false);
        result.put("independentPaperQualificationAllowed",false);
        result.put("liveAllowed",false);
      }''')
    text=once(text,'  private static long atFrom(JsonNode row) {', '''  static Map<String,Object> runPartial(Path tape,Path out,ResearchConfig cfg,
      AccountLedger.Limits limits,ObjectMapper mapper,OfflineSessionLabels pool,boolean candidate) throws Exception {
    if(pool==null || pool.profile()!=OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0)
      throw new IllegalArgumentException("Explicit strict partial pool required");
    return runInternal(tape,out,cfg,limits,mapper,false,Long.MIN_VALUE,Long.MAX_VALUE,"",
        false,null,false,null,pool,candidate);
  }

  private static long atFrom(JsonNode row) {''')
    return text

def materialize(output):
    result=strategy(output);root=Path(output)
    target=root/SOURCE.parent/'NativeFullTapeReplay.java'
    target.write_text(render(SOURCE.read_text()))
    result=dict(scope='STRICT_ORIGINAL_PARSER_RUNNER_NOT_FULL_COVERAGE_OR_QUALIFICATION',
        originalReplaySha256=SOURCE_SHA,generatedRunnerSha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        originalCoreFilesModified=0,originalFramesTimersAndSequencePreserved=True,
        unknownObservationPolicy='FAIL_CLOSED_NO_SKIP_NO_PUBLIC_AGGREGATE_FALLBACK',
        strategyBuild=result,liveAllowed=False,independentPaperQualificationAllowed=False)
    (root/'full-runner-provenance.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(materialize(a.output),indent=2))
