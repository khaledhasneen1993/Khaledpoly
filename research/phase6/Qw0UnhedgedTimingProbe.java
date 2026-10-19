package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** CONDITIONAL no-further-fill cancellation clock only, never a financial replay. */
public final class Qw0UnhedgedTimingProbe {
  static final ObjectMapper M=Qw0CausalProbe.M;
  static JsonNode node(Object o){return M.valueToTree(o);}
  static boolean sameAck(JsonNode a,JsonNode b) {
    return a!=null&&b!=null&&a.path("originalSequence").asLong(-1)==b.path("originalSequence").asLong(-2)
        &&a.path("eventIndex").asInt(-1)==b.path("eventIndex").asInt(-2)
        &&a.path("at").asLong(-1)==b.path("at").asLong(-2)&&a.path("kind").asText().equals(b.path("kind").asText());
  }
  public static void main(String[] args)throws Exception {
    if(args.length==1&&args[0].equals("--self-test")) {
      var ack=node(Map.of("originalSequence",1L,"eventIndex",0,"at",1792269759566L,"kind","BOOK"));
      if(!sameAck(ack,M.readTree(M.writeValueAsString(ack)))||sameAck(ack,node(Map.of("originalSequence",2,"eventIndex",0,"at",1792269759566L,"kind","BOOK"))))
        throw new AssertionError("Numeric source-anchor roundtrip/difference comparison failed");
      System.out.println("2 source-anchor numeric representation regressions passed");return;
    }
    if(args.length!=3)throw new IllegalArgumentException("context.gz evidence report");
    JsonNode context;try(var in=new GZIPInputStream(Files.newInputStream(Path.of(args[0])))){context=M.readTree(in);}
    var evidence=M.readTree(Files.readString(Path.of(args[1])));var s=evidence.path("state");
    if(s.path("originalSequence").asLong()!=243583||!evidence.path("furtherCounterpartAllocationsSuppressed").asBoolean())throw new AssertionError("Wrong conditional gate");
    var cfg=evidence.path("config");var checks=new HashMap<Long,JsonNode>();
    evidence.path("checks").forEach(c->checks.put(c.path("originalSequence").asLong(),c));
    var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));var pair=new HashSet<String>();s.path("quotes").forEach(q->pair.add(q.path("token").asText()));
    var q=s.path("quotes").get(1);var observed=new ArrayList<Object>();boolean submitted=false,requested=false;JsonNode ack=null;
    outer:for(var rec:context.path("records")) {
      var row=rec.path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();String kind=row.path("kind").asText().substring(9);var data=row.path("data");
      var events=kind.equals("FRAME")?data.path("events"):node(List.of(Map.of("kind",kind,"data",data)));int ix=0;
      for(var event:events) {
        String k=event.path("kind").asText();var v=event.path("data");
        if(k.equals("BOOK"))Qw0CausalProbe.noFill(e.accept(k,at,v));
        else if(k.equals("TRADE")||k.equals("TICK"))Qw0CausalProbe.noFill(e.accept("TICK",at,v));
        else if(k.equals("GAP")||k.equals("FEED_ERROR")) {
          var affected=new HashSet<String>();v.path("tokens").forEach(t->affected.add(t.asText()));if(v.has("token"))affected.add(v.path("token").asText());
          if(affected.isEmpty()||affected.stream().anyMatch(pair::contains))Qw0CausalProbe.noFill(e.accept("GAP",at,node(Map.of("tokens",pair,"reason",v.path("reason").asText("unknown")))));
          else Qw0CausalProbe.noFill(e.accept("GAP",at,v));
        }
        if(requested&&e.diagnostics().get(0).get("terminalMs")!=null) {
          ack=node(Map.of("originalSequence",seq,"eventIndex",ix,"at",at,"kind",k));break outer;
        }
        ix++;
      }
      if(seq==243583) {e.accept("ORDER",at,node(Map.of("id","qw0-conditional-b","token",q.path("token").asText(),"side","BUY",
          "price",q.path("price").asText(),"size",q.path("quantity").asText())));submitted=true;}
      var c=checks.get(seq);
      if(c!=null) {
        long wait=PairPolicy.secondLegWaitMs(c.path("remainingMs").asLong(),cfg.path("unhedgedMs").asLong(),new BigDecimal(c.path("volatility").asText()));
        boolean overdue=c.path("ageMs").asLong()>=cfg.path("unhedgedMs").asLong()
            ||new BigDecimal(q.path("quantity").asText()).compareTo(new BigDecimal(cfg.path("maxUnhedged").asText()))>=0;
        String reason=c.path("ageMs").asLong()<wait&&!overdue?"WAIT_SECOND_LEG":"CANCEL_BEFORE_EXIT";
        if(wait!=c.path("waitMs").asLong()||overdue!=c.path("overdue").asBoolean()||!reason.equals(c.path("reason").asText()))throw new AssertionError("Actual PairPolicy wait differs");
        if(!submitted||e.diagnostics().get(0).get("terminalMs")!=null)throw new AssertionError("Conditional B already terminal");
        observed.add(Map.of("originalSequence",seq,"at",at,"waitMs",wait,"reason",reason));
        if(reason.equals("CANCEL_BEFORE_EXIT")){e.accept("CANCEL",at,node(Map.of("id","qw0-conditional-b","reason","CANCEL_BEFORE_RISK_EXIT")));requested=true;}
      }
    }
    if(!sameAck(ack,evidence.path("expectedFirstDueEngineEvent")))throw new AssertionError("Actual cancel acknowledgement differs");
    var diag=e.diagnostics().get(0);if(!diag.get("terminalReason").equals("CANCEL_BEFORE_RISK_EXIT"))throw new AssertionError("Wrong actual terminal reason");
    var out=new LinkedHashMap<String,Object>();out.put("scope","CONDITIONAL_NO_FURTHER_ALLOCATIONS_WAIT_CANCEL_NOT_ACCOUNT");
    out.put("originalSequence",243583);out.put("actualPairPolicyChecks",observed);out.put("actualCancelAck",ack);out.put("diagnostic",diag);
    out.put("allTradeVolumeSuppressed",true);out.put("furtherCounterpartAllocationsSuppressed",true);out.put("accountRiskAndOtherMarketsOmitted",true);
    out.put("fillsCreated",0);out.put("candidateAccountSimulated",false);out.put("netPnlRecomputed",false);out.put("liveAllowed",false);
    out.put("independentPaperQualificationAllowed",false);Files.writeString(Path.of(args[2]),M.writerWithDefaultPrettyPrinter().writeValueAsString(out)+"\n");
  }
}
