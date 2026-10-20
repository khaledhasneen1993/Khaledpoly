package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.nio.file.*;
import java.math.BigDecimal;
import java.util.*;

/** Explicit research CLI: no market/network clients, state recovery, skips or live wiring. */
public final class NativeReplaySupport {
  static final ObjectMapper M=new ObjectMapper().findAndRegisterModules();
  static final class AuditedLabels implements OfflineSessionLabels {
    final ConservedReceiptPool pool; Map<String,Object> last=Map.of();
    AuditedLabels(JsonNode root){pool=new ConservedReceiptPool(root,M);}
    public SettlementReplayLabels.Binding resolve(long seq,int index,long at,JsonNode trade) {
      var n=new LinkedHashMap<String,Object>();n.put("seq",seq);n.put("eventIndex",index);n.put("at",at);
      n.put("observation",trade.deepCopy());last=n;
      return pool.resolve(seq,index,at,trade);
    }
    public Map<String,Object> report(){var n=new LinkedHashMap<String,Object>(pool.report());n.put("lastAttemptedOriginalObservation",last);return n;}
    public void requireConsumed(){pool.requireConsumed();}
    public Profile profile(){return Profile.MIXED_BINDING_BRIDGE0;}
  }
  static void failure(Path out,ObjectMapper mapper,JsonNode row,Map<String,Object> session,
      Object ledger,List<Map<String,Object>> audit,OfflineSessionLabels pool,boolean candidate,Exception error)throws Exception {
    var result=new LinkedHashMap<String,Object>();result.put("scope","INCOMPLETE_ORIGINAL_TAPE_FAIL_CLOSED_DIAGNOSTIC_NOT_FINANCIAL_RESULT");
    result.put("candidateFrozenPoliciesEnabled",candidate);result.put("decision","NO_GO");
    result.put("row",row==null?null:Map.of("seq",row.path("seq"),"arrivalMs",row.path("arrivalMs"),"kind",row.path("kind")));
    result.put("labels",pool==null?null:pool.report());result.put("sessionAfterSuspension",session);result.put("ledgerAfterSuspension",ledger);
    var causes=new ArrayList<String>();for(Throwable c=error;c!=null;c=c.getCause())causes.add(c.getClass().getSimpleName()+": "+c.getMessage());result.put("errors",causes);
    for(String flag:List.of("fullOriginalTapeCoverageProven","completeAccountComparisonPerformed","marketNetPnlRecomputed","independentPaperQualificationAllowed","liveAllowed"))result.put(flag,false);
    Files.writeString(out.resolve("failure.json"),mapper.writerWithDefaultPrettyPrinter().writeValueAsString(result)+"\n");
    try(var writer=Files.newBufferedWriter(out.resolve("failure-audit.jsonl"))) {
      for(var event:audit){writer.write(mapper.writeValueAsString(event));writer.newLine();}
    }
  }
  static AccountLedger.Limits limits(){return new AccountLedger.Limits(new BigDecimal("25"),new BigDecimal("25"),new BigDecimal("250"),new BigDecimal("25"),new BigDecimal("50"));}
  public static void main(String[] args)throws Exception {
    if(args.length!=5||!Set.of("baseline","candidate").contains(args[4]))throw new IllegalArgumentException("original-tape new-output config pool.json baseline|candidate");
    Path config=Path.of(args[2]);
    if(!ClosedLoopReplay.sha256(config).equals("a84b6b3283e15b0069aafe615d19abeebda8f3e4104467ed1111983ab5ddbc00"))throw new IllegalArgumentException("Frozen config required");
    var cfg=M.readValue(Files.readString(config),ResearchConfig.class);
    var pool=new AuditedLabels(M.readTree(Files.readString(Path.of(args[3]))));
    NativeFullTapeReplay.runPartial(Path.of(args[0]),Path.of(args[1]),cfg,limits(),M,pool,args[4].equals("candidate"));
  }
}
