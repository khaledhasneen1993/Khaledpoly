package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Conditional original resting policy with unchanged hypothetical counterpart; NOT an account. */
public final class Qw0RestingProbe {
  static final ObjectMapper M=Qw0CausalProbe.M;
  static BigDecimal d(JsonNode n){return Qw0CausalProbe.dec(n);}
  static JsonNode node(Object o){return M.valueToTree(o);}
  static String reason(JsonNode c,JsonNode evidence) {
    var market=evidence.path("seedWitness").path("market");var cfg=evidence.path("config");var state=evidence.path("state");
    var a=c.path("firstBook");var b=c.path("secondBook");var tick=d(market.path("tick"));
    var depth=d(a.path("bids").get(0).path("size")).min(d(b.path("bids").get(0).path("size")));
    var required=PairPolicy.requiredEdge(d(cfg.path("minimumEdge")),d(c.path("volatility")),
        (market.path("endMs").asLong()-c.path("at").asLong())/1000,depth,cfg.path("activationMs").asLong(),BigDecimal.ZERO);
    var pa=d(state.path("quotes").get(0).path("price"));var pb=d(state.path("quotes").get(1).path("price"));
    var q=d(state.path("targetQuote").path("quantity"));var cost=d(cfg.path("mergeCost"));
    var net=BigDecimal.ONE.subtract(pa).subtract(pb).multiply(q).subtract(cost);
    if(required.compareTo(d(c.path("requiredEdge")))!=0||net.compareTo(d(c.path("reservedNetEdgeTotal")))!=0)
      throw new AssertionError("Actual PairPolicy or original resting net differs");
    if(pa.remainder(tick).signum()!=0||pb.remainder(tick).signum()!=0
        ||pa.compareTo(d(a.path("asks").get(0).path("price")))>=0||pb.compareTo(d(b.path("asks").get(0).path("price")))>=0)return "RESTING_PRICE_INVALID";
    if(net.compareTo(required.multiply(q))<0)return "RESTING_NET_EDGE";
    var ap=d(a.path("bids").get(0).path("price")).add(tick).min(d(a.path("asks").get(0).path("price")).subtract(tick)).divide(tick,0,RoundingMode.FLOOR).multiply(tick);
    var bp=d(b.path("bids").get(0).path("price")).add(tick).min(d(b.path("asks").get(0).path("price")).subtract(tick)).divide(tick,0,RoundingMode.FLOOR).multiply(tick);
    var size=d(cfg.path("orderShares")).min(depth.multiply(new BigDecimal(".1"))).setScale(2,RoundingMode.DOWN);
    boolean improve=pa.compareTo(d(a.path("bids").get(0).path("price")))<0||pb.compareTo(d(b.path("bids").get(0).path("price")))<0;
    boolean lawful=ap.signum()>0&&bp.signum()>0&&ap.compareTo(d(a.path("asks").get(0).path("price")))<0&&bp.compareTo(d(b.path("asks").get(0).path("price")))<0;
    if(improve&&lawful&&size.compareTo(d(market.path("minSize")))>=0
        &&BigDecimal.ONE.subtract(ap).subtract(bp).multiply(size).subtract(cost).compareTo(required.multiply(size))>=0
        &&c.path("at").asLong()-state.path("submitMs").asLong()>=2000)return "REPRICE_VALIDATED_PAIR";
    return "RESTING";
  }
  public static void main(String[] args)throws Exception {
    if(args.length!=4)throw new IllegalArgumentException("context.gz bindings evidence report");
    JsonNode context;try(var in=new GZIPInputStream(Files.newInputStream(Path.of(args[0])))){context=M.readTree(in);}
    var manifest=M.readTree(Files.readString(Path.of(args[1])));var evidence=M.readTree(Files.readString(Path.of(args[2])));
    var s=manifest.path("state");if(!s.equals(evidence.path("state"))||s.path("originalSequence").asLong()!=243583)throw new AssertionError("Wrong frozen state");
    var pair=new HashSet<String>();manifest.path("pair").forEach(t->pair.add(t.asText()));
    var labels=new HashMap<String,JsonNode>();for(var b:manifest.path("bindings"))labels.put(b.path("seq").asLong()+":"+b.path("eventIndex").asInt(),b);
    var checks=new HashMap<Long,JsonNode>();for(var c:evidence.path("checks"))checks.put(c.path("originalSequence").asLong(),c);
    var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));var fills=new ArrayList<PaperMatchingEngine.Fill>();
    String target=s.path("targetQuote").path("token").asText();long requested=-1;String cancelReason=null;int checked=0,consumed=0;
    for(var rec:context.path("records")) {
      var row=rec.path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();
      if(at>evidence.path("fixedHorizonMs").asLong())break;
      String kind=row.path("kind").asText().substring(9);var data=row.path("data");
      var events=kind.equals("FRAME")?data.path("events"):node(List.of(Map.of("kind",kind,"data",data)));int ix=0;
      for(var ev:events) {
        String k=ev.path("kind").asText();var v=ev.path("data");var binding=labels.get(seq+":"+ix);
        if(k.equals("TRADE")&&binding!=null) {fills.addAll(e.acceptSettlement(at,v,Qw0CausalProbe.binding(binding,v,seq,ix,at,pair)).fills());consumed++;}
        else if(k.equals("TRADE")||k.equals("TICK"))Qw0CausalProbe.noFill(e.accept("TICK",at,v));
        else if(k.equals("BOOK"))Qw0CausalProbe.noFill(e.accept(k,at,v));
        else if(k.equals("GAP")||k.equals("FEED_ERROR")) {
          var affected=new HashSet<String>();v.path("tokens").forEach(t->affected.add(t.asText()));if(v.has("token"))affected.add(v.path("token").asText());
          if(affected.isEmpty()||affected.stream().anyMatch(pair::contains))Qw0CausalProbe.noFill(e.accept("GAP",at,node(Map.of("tokens",pair,"reason",v.path("reason").asText("unknown")))));
          else Qw0CausalProbe.noFill(e.accept("GAP",at,v));
        }
        ix++;
      }
      if(seq==243583) {var q=s.path("targetQuote");e.accept("ORDER",at,node(Map.of("id","qw0-target-resting","token",target,
          "side","BUY","price",q.path("price").asText(),"size",q.path("quantity").asText())));}
      var check=checks.get(seq);
      // Strategy decides after ALL events in a frame. Stop maintaining an untouched pair on target fill.
      if(fills.isEmpty()&&check!=null&&requested<0) {
        String r=reason(check,evidence);checked++;
        if(!r.equals(check.path("reason").asText())||at!=check.path("at").asLong())throw new AssertionError("Resting reason/time differs");
        if(!r.equals("RESTING")){requested=at;cancelReason=r;e.accept("CANCEL",at,node(Map.of("id","qw0-target-resting","reason",r)));}
      }
    }
    var out=new LinkedHashMap<String,Object>();out.put("scope","CONDITIONAL_TARGET_RESTING_LIFETIME_UNKNOWN_COUNTERPART_NOT_ACCOUNT");
    out.put("originalSequence",243583);out.put("actualPairPolicyChecks",checked);out.put("consumedTargetBindings",consumed);
    out.put("cancelRequestMs",requested);out.put("cancelReason",cancelReason);out.put("diagnostics",e.diagnostics());
    out.put("conditionalTargetAllocations",fills);out.put("counterpartExecutionOmitted",true);out.put("counterpartRemainsUntouchedAssumed",true);
    out.put("actualBotFillsCreated",0);out.put("candidateAccountSimulated",false);out.put("netPnlRecomputed",false);
    out.put("independentPaperQualificationAllowed",false);out.put("liveAllowed",false);
    Files.writeString(Path.of(args[3]),M.writerWithDefaultPrettyPrinter().writeValueAsString(out)+"\n");
  }
}
