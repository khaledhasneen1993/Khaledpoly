package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Actual both-order component/risk/hedge prefix through original GAP, NOT full account. */
public final class Qw0ThroughGapProbe {
  static final ObjectMapper M=Qw0CausalProbe.M;
  static JsonNode node(Object x){return M.valueToTree(x);}
  static BigDecimal d(JsonNode x){return Qw0CausalProbe.dec(x);}
  static boolean advances(String kind,JsonNode events){return !kind.equals("FRAME")||!events.isEmpty();}
  static BigDecimal best(JsonNode book,String side,boolean high) {
    BigDecimal result=null;for(var level:book.path(side)){var price=d(level.path("price"));result=result==null?price:high?result.max(price):result.min(price);}
    if(result==null)throw new AssertionError("Missing causal hedge depth");return result;
  }
  public static void main(String[] args)throws Exception {
    if(args.length==1&&args[0].equals("--self-test")) {
      var empty=node(List.of());var book=node(List.of(Map.of("kind","BOOK","data",Map.of())));
      if(advances("FRAME",empty)||!advances("FRAME",book)||!advances("TICK",empty))throw new AssertionError("Empty-frame strategy callback ordering differs");
      System.out.println("3 empty/nonempty frame and standalone callback ordering assertions passed");return;
    }
    if(args.length!=4)throw new IllegalArgumentException("context.gz bindings evidence report");
    JsonNode context;try(var in=new GZIPInputStream(Files.newInputStream(Path.of(args[0])))){context=M.readTree(in);}
    var manifest=M.readTree(Files.readString(Path.of(args[1])));var evidence=M.readTree(Files.readString(Path.of(args[2])));
    var prefix=evidence.path("prefix");var timing=evidence.path("timing");var s=manifest.path("state");var cfg=prefix.path("config");
    if(s.path("originalSequence").asLong()!=243583||!s.equals(prefix.path("state")))throw new AssertionError("Wrong selected original state");
    var pair=new HashSet<String>();manifest.path("pair").forEach(t->pair.add(t.asText()));
    var labels=new HashMap<String,JsonNode>();for(var b:manifest.path("bindings"))if(labels.putIfAbsent(b.path("seq").asLong()+":"+b.path("eventIndex").asInt(),b)!=null)throw new AssertionError("Duplicate original source group");
    if(labels.size()!=148)throw new AssertionError("Complete148 original groups required");
    var resting=new HashMap<Long,JsonNode>();prefix.path("checks").forEach(c->resting.put(c.path("originalSequence").asLong(),c));
    var waiting=new HashMap<Long,JsonNode>();timing.path("checks").forEach(c->waiting.put(c.path("originalSequence").asLong(),c));
    var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));var fills=new ArrayList<PaperMatchingEngine.Fill>();
    var books=new HashMap<String,JsonNode>();var seen=new HashSet<String>();var decisions=new ArrayList<Object>();
    String lead=s.path("quotes").get(0).path("token").asText(),other=s.path("quotes").get(1).path("token").asText();
    long request=timing.path("conditionalCancelRequest").path("at").asLong(),ackAt=timing.path("expectedFirstDueEngineEvent").path("at").asLong();
    boolean submitted=false,cancelSent=false,gap=false,hedged=false;Map<String,Object> hedge=null;long pendingTakerDue=-1;
    for(var rec:context.path("records")) {
      var row=rec.path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();if(at>manifest.path("horizonMs").asLong())break;
      String kind=row.path("kind").asText().substring(9);var data=row.path("data");
      var events=kind.equals("FRAME")?data.path("events"):node(List.of(Map.of("kind",kind,"data",data)));int ix=0;
      for(var event:events) {
        String k=event.path("kind").asText();var v=event.path("data");String key=seq+":"+ix;var binding=labels.get(key);
        if(k.equals("BOOK")) {
          Qw0CausalProbe.noFill(e.accept(k,at,v));String token=v.path("token").asText();long source=v.path("sourceMs").asLong(-1);var old=books.get(token);
          if(source<0||source>at||at-source>2000||old!=null&&source<old.path("sourceMs").asLong())books.remove(token);else books.put(token,v);
        }
        else if(k.equals("TRADE")&&binding!=null) {if(!seen.add(key))throw new AssertionError("Duplicate original group consumption");fills.addAll(e.acceptSettlement(at,v,Qw0CausalProbe.binding(binding,v,seq,ix,at,pair)).fills());}
        else if(k.equals("TICK")||k.equals("TRADE")) {
          if(k.equals("TRADE")&&submitted&&pair.contains(v.path("token").asText())&&v.path("sourceMs").asLong()>=s.path("activationDueMs").asLong()) {
            if(at<=ackAt)throw new AssertionError("Missing conserved original group before ACK");
            for(var o:e.diagnostics())if(o.get("terminalMs")==null&&(o.get("activatedMs")!=null||at>=((Number)o.get("activationDueMs")).longValue()))throw new AssertionError("Unknown print with potentially executable order");
          }
          Qw0CausalProbe.noFill(e.accept("TICK",at,v));
        } else if(k.equals("GAP")||k.equals("FEED_ERROR")) {
          var affected=new HashSet<String>();v.path("tokens").forEach(t->affected.add(t.asText()));if(v.has("token"))affected.add(v.path("token").asText());
          if(affected.isEmpty()||affected.stream().anyMatch(pair::contains)) {
            Qw0CausalProbe.noFill(e.accept("GAP",at,node(Map.of("tokens",pair,"reason",v.path("reason").asText("unknown")))));pair.forEach(books::remove);
            if(submitted){if(at!=manifest.path("horizonMs").asLong())throw new AssertionError("Earlier scoped GAP");gap=true;}
          }else Qw0CausalProbe.noFill(e.accept("GAP",at,v));
        }
        ix++;
      }
      if(seq==243583) {int i=0;for(var q:s.path("quotes"))e.accept("ORDER",at,node(Map.of("id","qw0-gap-"+(i++),"token",q.path("token").asText(),"side","BUY","price",q.path("price").asText(),"size",q.path("quantity").asText())));submitted=true;}
      var r=resting.get(seq);
      if(r!=null) {
        if(!fills.isEmpty()||!Qw0RestingProbe.reason(r,prefix).equals("RESTING"))throw new AssertionError("Pre-fill resting branch changed");
        for(var o:e.diagnostics())if(o.get("terminalMs")!=null||o.get("activatedMs")==null||new BigDecimal(o.get("remainingShares").toString()).compareTo(new BigDecimal("5"))!=0)throw new AssertionError("Pre-fill pair not intact");
        decisions.add(Map.of("at",at,"seq",seq,"reason","RESTING"));
      }
      var w=waiting.get(seq);
      if(w!=null) {
        if(fills.size()!=1||!fills.get(0).token().equals(lead)||fills.get(0).size().compareTo(new BigDecimal("5"))!=0||fills.get(0).at()!=timing.path("firstModelAllocationMs").asLong())throw new AssertionError("Actual unhedged branch invalidated by counterpart allocation");
        long wait=PairPolicy.secondLegWaitMs(w.path("remainingMs").asLong(),cfg.path("unhedgedMs").asLong(),d(w.path("volatility")));
        if(wait!=w.path("waitMs").asLong())throw new AssertionError("Actual wait differs");
        String reason=w.path("ageMs").asLong()<wait&&!w.path("overdue").asBoolean()?"WAIT_SECOND_LEG":"CANCEL_BEFORE_EXIT";
        decisions.add(Map.of("at",at,"seq",seq,"reason",reason));
        if(reason.equals("CANCEL_BEFORE_EXIT")){if(at!=request)throw new AssertionError("Changed actual cancel request");e.accept("CANCEL",at,node(Map.of("id","qw0-gap-1","reason","CANCEL_BEFORE_RISK_EXIT")));cancelSent=true;}
      }
      if(cancelSent&&!hedged&&advances(kind,events)&&at>=ackAt&&!gap) {
        var b=e.diagnostics().get(1);if(!Objects.equals(b.get("terminalReason"),"CANCEL_BEFORE_RISK_EXIT")||((Number)b.get("terminalMs")).longValue()!=ackAt)throw new AssertionError("Actual counterpart cancel differs");
        if(at!=ackAt||seq!=timing.path("expectedFirstDueEngineEvent").path("originalSequence").asLong())throw new AssertionError("Wrong first post-ACK frame callback");
        var market=prefix.path("seedWitness").path("market");var fee=new FeeModel(d(market.path("feeRate")).multiply(d(cfg.path("feeMultiplier"))),market.path("feeExponent").asInt());
        var lb=books.get(lead);var ob=books.get(other);var tick=d(market.path("tick"));var quantity=new BigDecimal("5");var basis=d(s.path("quotes").get(0).path("price"));
        if(lb==null||ob==null||at-lb.path("sourceMs").asLong()>2000||at-ob.path("sourceMs").asLong()>2000)throw new AssertionError("No causal fresh hedge books");
        var leadBid=best(lb,"bids",true);var leadAsk=best(lb,"asks",false);var otherAsk=best(ob,"asks",false);
        var choice=PairPolicy.hedge(basis,otherAsk,leadBid,fee.fee(BigDecimal.ONE,otherAsk,false).add(d(cfg.path("mergeCost")).divide(quantity,18,RoundingMode.UP)),fee.fee(BigDecimal.ONE,leadBid,false),d(cfg.path("minimumEdge")),false);
        hedge=new LinkedHashMap<>();hedge.put("at",at);hedge.put("originalSequence",seq);hedge.put("choice",choice);hedge.put("leadBid",leadBid);hedge.put("leadAsk",leadAsk);hedge.put("otherAsk",otherAsk);
        hedge.put("sourceLead",lb.path("sourceMs").asLong());hedge.put("sourceOther",ob.path("sourceMs").asLong());hedge.put("accountRiskAssumedAvailable",true);
        if(choice.action().equals("COMPLETE")){pendingTakerDue=at+250;hedge.put("plannedAction","POSITIVE_EDGE_COMPLETION");hedge.put("plannedDueMs",pendingTakerDue);}
        else {
          var price=leadAsk.subtract(tick).max(leadBid.add(tick));var worst=price.subtract(basis).multiply(quantity).negate().max(BigDecimal.ZERO);
          if(price.compareTo(BigDecimal.ONE)>=0||quantity.compareTo(d(market.path("minSize")))<0||worst.compareTo(d(cfg.path("maxExitLoss")))>0)throw new AssertionError("Unmodelled reduction rejection");
          e.accept("ORDER",at,node(Map.of("id","qw0-gap-reduction","token",lead,"side","SELL","price",price,"size",quantity)));
          hedge.put("plannedAction","MAKER_REDUCTION");hedge.put("price",price);hedge.put("plannedDueMs",at+250);
        }
        if(at+250<=manifest.path("horizonMs").asLong())throw new AssertionError("Hedge executable before GAP requires additional complete receipt/action evidence");hedged=true;
      }
      if(gap)break;
    }
    if(!gap||!hedged||seen.size()!=148||fills.size()!=1)throw new AssertionError("Incomplete actual original prefix through GAP");
    var out=new LinkedHashMap<String,Object>();out.put("scope","ACTUAL_COMPONENT_PREFIX_WAIT_CANCEL_FIRST_REDUCTION_GAP_NOT_ACCOUNT");out.put("originalSequence",243583);
    out.put("consumedOriginalGroups",seen.size());out.put("decisions",decisions);out.put("hedgeDecision",hedge);out.put("diagnostics",e.diagnostics());out.put("modelAllocations",fills);
    out.put("actualComponentAllocationDiagnostics",e.settlementDiagnostics());out.put("firstScopedGapMs",manifest.path("horizonMs").asLong());out.put("pendingTakerCanceledByGap",pendingTakerDue>=0);
    out.put("remainingUnhedgedShares",new BigDecimal("5"));out.put("accountRiskAndOtherMarketsOmitted",true);out.put("postGapAndResolutionOmitted",true);
    out.put("actualBotFillsCreated",0);out.put("candidateAccountSimulated",false);out.put("netPnlRecomputed",false);out.put("independentPaperQualificationAllowed",false);out.put("liveAllowed",false);
    Files.writeString(Path.of(args[3]),M.writerWithDefaultPrettyPrinter().writeValueAsString(out)+"\n");
  }
}
