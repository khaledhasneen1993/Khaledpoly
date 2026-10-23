package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Actual two-order matcher and original resting checks, stopping before hedge/account logic. */
public final class Qw0PairPrefixProbe {
  static final ObjectMapper M=Qw0CausalProbe.M;
  static JsonNode node(Object v){return M.valueToTree(v);}
  static BigDecimal d(Object v){return new BigDecimal(v.toString());}
  public static void main(String[] args)throws Exception {
    if(args.length!=4)throw new IllegalArgumentException("context.gz bindings evidence report");
    JsonNode context;try(var in=new GZIPInputStream(Files.newInputStream(Path.of(args[0])))){context=M.readTree(in);}
    var manifest=M.readTree(Files.readString(Path.of(args[1])));var evidence=M.readTree(Files.readString(Path.of(args[2])));
    var s=manifest.path("state");if(!s.equals(evidence.path("state"))||s.path("originalSequence").asLong()!=243583
        ||manifest.path("counterpartExecutionOmitted").asBoolean(true))throw new AssertionError("Wrong complete prefix scope");
    var pair=new HashSet<String>();manifest.path("pair").forEach(t->pair.add(t.asText()));
    var labels=new HashMap<String,JsonNode>();for(var b:manifest.path("bindings"))
      if(labels.putIfAbsent(b.path("seq").asLong()+":"+b.path("eventIndex").asInt(),b)!=null)throw new AssertionError("Duplicate source label");
    if(labels.size()!=40)throw new AssertionError("Complete40 original prefix groups required");
    var checks=new HashMap<Long,JsonNode>();evidence.path("checks").forEach(c->checks.put(c.path("originalSequence").asLong(),c));
    var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));var fills=new ArrayList<PaperMatchingEngine.Fill>();
    var audit=new ArrayList<Object>();var seen=new HashSet<String>();boolean submitted=false;String rejection=null;
    long lastSeq=-1;var checkResults=new ArrayList<Object>();
    for(var rec:context.path("records")) {
      var row=rec.path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();
      if(at>manifest.path("fixedHorizonMs").asLong())break;lastSeq=seq;
      String kind=row.path("kind").asText().substring(9);var data=row.path("data");
      var events=kind.equals("FRAME")?data.path("events"):node(List.of(Map.of("kind",kind,"data",data)));int ix=0;
      for(var ev:events) {
        String k=ev.path("kind").asText();var v=ev.path("data");String key=seq+":"+ix;var b=labels.get(key);
        if(k.equals("TRADE")&&b!=null) {
          if(!seen.add(key))throw new AssertionError("Reused original observation");
          var update=e.acceptSettlement(at,v,Qw0CausalProbe.binding(b,v,seq,ix,at,pair));fills.addAll(update.fills());
          audit.add(Map.of("seq",seq,"eventIndex",ix,"at",at,"sourceMs",v.path("sourceMs").asLong(),"allocations",update.fills()));
        } else if(k.equals("TRADE")||k.equals("TICK")) {
          if(k.equals("TRADE")&&submitted&&pair.contains(v.path("token").asText())&&v.path("sourceMs").asLong()>=s.path("activationDueMs").asLong())
            throw new AssertionError("No aggregate fallback for unknown pair receipt");
          Qw0CausalProbe.noFill(e.accept("TICK",at,v));
        } else if(k.equals("BOOK"))Qw0CausalProbe.noFill(e.accept(k,at,v));
        else if(k.equals("GAP")||k.equals("FEED_ERROR")) {
          var affected=new HashSet<String>();v.path("tokens").forEach(t->affected.add(t.asText()));if(v.has("token"))affected.add(v.path("token").asText());
          if(affected.isEmpty()||affected.stream().anyMatch(pair::contains))Qw0CausalProbe.noFill(e.accept("GAP",at,node(Map.of("tokens",pair,"reason",v.path("reason").asText("unknown")))));
          else Qw0CausalProbe.noFill(e.accept("GAP",at,v));
        }
        ix++;
      }
      if(!fills.isEmpty()&&fills.get(0).at()!=manifest.path("fixedHorizonMs").asLong())
        throw new AssertionError("Earlier model allocation needs actual hedge lifecycle; do not continue an untouched pair");
      if(seq==243583) {
        if(at!=s.path("submitMs").asLong())throw new AssertionError("Changed submission time");
        int i=0;for(var q:s.path("quotes"))e.accept("ORDER",at,node(Map.of("id","qw0-pair-"+(i++),"token",q.path("token").asText(),
            "side","BUY","price",q.path("price").asText(),"size",q.path("quantity").asText())));submitted=true;
      }
      var check=checks.get(seq);
      if(submitted&&fills.isEmpty()&&rejection==null&&check!=null) {
        var diagnostics=e.diagnostics();boolean intact=diagnostics.size()==2;
        for(var diagnostic:diagnostics)intact&=diagnostic.get("terminalMs")==null&&diagnostic.get("activatedMs")!=null
            &&d(diagnostic.get("remainingShares")).compareTo(new BigDecimal("5"))==0;
        String reason=intact?Qw0RestingProbe.reason(check,evidence):"RESTING_INCOMPLETE_PAIR";
        checkResults.add(Map.of("seq",seq,"at",at,"bothActiveEqualRemaining",intact,"reason",reason));
        if(!reason.equals("RESTING")) {
          rejection=reason;
          for(var diagnostic:diagnostics)if(diagnostic.get("terminalMs")==null)e.accept("CANCEL",at,node(Map.of("id",diagnostic.get("id"),"reason",reason)));
        }
      }
    }
    if(!submitted||seen.size()!=40)throw new AssertionError("Missing full source prefix consumption");
    var out=new LinkedHashMap<String,Object>();out.put("scope","BOTH_ACTUAL_ORDER_PREFIX_MODEL_NOT_FULL_STRATEGY_ACCOUNT");
    out.put("originalSequence",243583);out.put("fixedHorizonMs",manifest.path("fixedHorizonMs").asLong());out.put("lastOriginalSequence",lastSeq);
    out.put("completeOriginalBindingsConsumed",seen.size());out.put("restingChecks",checkResults);out.put("prefixRejectionReason",rejection);
    out.put("diagnostics",e.diagnostics());out.put("receiptAudit",audit);out.put("modelAllocations",fills);
    out.put("actualComponentAllocationDiagnostics",e.settlementDiagnostics());out.put("counterpartExecutionOmitted",false);
    out.put("hedgeExitAndResolutionOmitted",true);out.put("actualBotFillsCreated",0);out.put("candidateAccountSimulated",false);
    out.put("netPnlRecomputed",false);out.put("independentPaperQualificationAllowed",false);out.put("liveAllowed",false);
    Files.writeString(Path.of(args[3]),M.writerWithDefaultPrettyPrinter().writeValueAsString(out)+"\n");
  }
}
