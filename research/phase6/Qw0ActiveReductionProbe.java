package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Separately frozen reduction gate, stops on first reduction fill. NOT account/PnL. */
public final class Qw0ActiveReductionProbe {
  static final ObjectMapper M=Qw0CausalProbe.M;
  static JsonNode node(Object x){return M.valueToTree(x);}
  static BigDecimal d(JsonNode x){return Qw0CausalProbe.dec(x);}
  static boolean advances(String kind,JsonNode events){return !kind.equals("FRAME")||!events.isEmpty();}
  static BigDecimal best(JsonNode book,String side,boolean high) {
    BigDecimal result=null;for(var level:book.path(side)){var price=d(level.path("price"));result=result==null?price:high?result.max(price):result.min(price);}
    if(result==null)throw new AssertionError("Missing causal hedge depth");return result;
  }
  static BigDecimal componentPrice(BigInteger cost,BigInteger shares,boolean buy) {
    return new BigDecimal(cost).divide(new BigDecimal(shares),28,buy?RoundingMode.UP:RoundingMode.DOWN);
  }
  static SettlementReplayLabels.Binding binding(JsonNode b,JsonNode trade,long seq,int ix,long at,Set<String> pair)throws Exception {
    var old=Qw0CausalProbe.binding(b,trade,seq,ix,at,pair);var portions=new ArrayList<SettlementReplayLabels.Portion>();
    for(var p:b.path("parts"))portions.add(new SettlementReplayLabels.Portion(p.path("identity").asText(),p.path("token").asText(),p.path("buy").asBoolean(),
        componentPrice(p.path("collateralRaw").bigIntegerValue(),p.path("sharesRaw").bigIntegerValue(),p.path("buy").asBoolean()),new BigDecimal(p.path("sharesRaw").bigIntegerValue(),6)));
    return new SettlementReplayLabels.Binding(old.seq(),old.index(),old.at(),old.source(),old.tradeHash(),old.token(),old.side(),old.price(),old.size(),old.pair(),List.copyOf(portions));
  }
  public static void main(String[] args)throws Exception {
    if(args.length==1&&args[0].equals("--self-test")) {
      var empty=node(List.of());var book=node(List.of(Map.of("kind","BOOK","data",Map.of())));
      if(advances("FRAME",empty)||!advances("FRAME",book)||!advances("TICK",empty))throw new AssertionError("Empty-frame strategy callback ordering differs");
      BigInteger den=BigInteger.TEN.pow(35),boundary=den.multiply(BigInteger.valueOf(51)).divide(BigInteger.valueOf(100));var limit=new BigDecimal(".51");
      if(componentPrice(boundary.subtract(BigInteger.ONE),den,false).compareTo(limit)>=0
          ||componentPrice(boundary.add(BigInteger.ONE),den,true).compareTo(limit)<=0
          ||componentPrice(boundary,den,false).compareTo(limit)!=0
          ||componentPrice(boundary,den,true).compareTo(limit)!=0)throw new AssertionError("Side-conservative integer boundary differs");
      System.out.println("3 callback and4 BUY-UP/SELL-DOWN boundary assertions passed");return;
    }
    if(args.length!=4)throw new IllegalArgumentException("context.gz bindings evidence report");
    JsonNode context;try(var in=new GZIPInputStream(Files.newInputStream(Path.of(args[0])))){context=M.readTree(in);}
    var manifest=M.readTree(Files.readString(Path.of(args[1])));var evidence=M.readTree(Files.readString(Path.of(args[2])));
    var prefix=evidence.path("prefix");var timing=evidence.path("timing");var s=manifest.path("state");var cfg=prefix.path("config");
    if(s.path("originalSequence").asLong()!=243583||!s.equals(prefix.path("state")))throw new AssertionError("Wrong selected original state");
    var pair=new HashSet<String>();manifest.path("pair").forEach(t->pair.add(t.asText()));
    var labels=new HashMap<String,JsonNode>();for(var b:manifest.path("bindings"))if(labels.putIfAbsent(b.path("seq").asLong()+":"+b.path("eventIndex").asInt(),b)!=null)throw new AssertionError("Duplicate original source group");
    if(labels.size()!=162)throw new AssertionError("Complete162 original groups required");
    var resting=new HashMap<Long,JsonNode>();prefix.path("checks").forEach(c->resting.put(c.path("originalSequence").asLong(),c));
    var waiting=new HashMap<Long,JsonNode>();timing.path("checks").forEach(c->waiting.put(c.path("originalSequence").asLong(),c));
    var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));var fills=new ArrayList<PaperMatchingEngine.Fill>();
    var books=new HashMap<String,JsonNode>();var seen=new HashSet<String>();var decisions=new ArrayList<Object>();
    String lead=s.path("quotes").get(0).path("token").asText(),other=s.path("quotes").get(1).path("token").asText();
    long request=timing.path("conditionalCancelRequest").path("at").asLong(),ackAt=timing.path("expectedFirstDueEngineEvent").path("at").asLong();
    boolean submitted=false,cancelSent=false,gap=false,hedged=false,stoppedOnReductionFill=false;long stopSeq=-1,nextReductionCheck=-1;int stopEvent=-1;Map<String,Object> hedge=null;long pendingTakerDue=-1;
    replay: for(var rec:context.path("records")) {
      var row=rec.path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();if(at>manifest.path("horizonMs").asLong())break;
      String kind=row.path("kind").asText().substring(9);var data=row.path("data");
      var events=kind.equals("FRAME")?data.path("events"):node(List.of(Map.of("kind",kind,"data",data)));int ix=0;
      for(var event:events) {
        String k=event.path("kind").asText();var v=event.path("data");String key=seq+":"+ix;var binding=labels.get(key);
        if(k.equals("BOOK")) {
          Qw0CausalProbe.noFill(e.accept(k,at,v));String token=v.path("token").asText();long source=v.path("sourceMs").asLong(-1);var old=books.get(token);
          if(source<0||source>at||at-source>2000||old!=null&&source<old.path("sourceMs").asLong())books.remove(token);else books.put(token,v);
        }
        else if(k.equals("TRADE")&&binding!=null) {if(!seen.add(key))throw new AssertionError("Duplicate original group consumption");var update=e.acceptSettlement(at,v,binding(binding,v,seq,ix,at,pair));fills.addAll(update.fills());
          if(hedged&&!update.fills().isEmpty()) {
            for(var f:update.fills())if(!f.id().equals("qw0-gap-reduction")||f.buy()||!f.token().equals(lead))throw new AssertionError("Unexpected post-hedge allocation");
            stoppedOnReductionFill=true;stopSeq=seq;stopEvent=ix;break replay;
          }}
        else if(k.equals("TICK")||k.equals("TRADE")) {
          if(k.equals("TRADE")&&submitted&&pair.contains(v.path("token").asText())&&v.path("sourceMs").asLong()>=s.path("activationDueMs").asLong()) {
            throw new AssertionError("Missing conserved original pair group before GAP");
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
        if(choice.action().equals("COMPLETE"))throw new AssertionError("Frozen original maker reduction changed to taker completion");
        else {
          var price=leadAsk.subtract(tick).max(leadBid.add(tick));var worst=price.subtract(basis).multiply(quantity).negate().max(BigDecimal.ZERO);
          if(price.compareTo(BigDecimal.ONE)>=0||quantity.compareTo(d(market.path("minSize")))<0||worst.compareTo(d(cfg.path("maxExitLoss")))>0)throw new AssertionError("Unmodelled reduction rejection");
          e.accept("ORDER",at,node(Map.of("id","qw0-gap-reduction","token",lead,"side","SELL","price",price,"size",quantity)));
          hedge.put("plannedAction","MAKER_REDUCTION");hedge.put("price",price);hedge.put("plannedDueMs",at+250);
        }
        hedged=true;nextReductionCheck=at+cfg.path("decisionMillis").asLong(250);
      }
      if(hedged&&!gap&&advances(kind,events)&&at>=nextReductionCheck) {
        nextReductionCheck=at+cfg.path("decisionMillis").asLong(250);
        var market=prefix.path("seedWitness").path("market");
        if(!market.path("accepting").asBoolean()||at<market.path("startMs").asLong()||at>=market.path("endMs").asLong()
            ||at-market.path("observedMs").asLong()>cfg.path("metadataMaxAgeMs").asLong())throw new AssertionError("New metadata/market cancellation requires full action gate");
        if(at-timing.path("firstModelAllocationMs").asLong()>=cfg.path("unhedgedMs").asLong()
            ||new BigDecimal("5").compareTo(d(cfg.path("maxUnhedged")))>=0)throw new AssertionError("New overdue/risk decision requires full account gate");
        for(String token:pair) {
          var book=books.get(token);
          if(book==null||at-book.path("sourceMs").asLong()>2000||book.path("bids").isEmpty()||book.path("asks").isEmpty())throw new AssertionError("New data cancellation requires complete action gate");
        }
        boolean openSell=false;for(var order:e.diagnostics())if(order.get("terminalMs")==null) {
          if(!order.get("id").equals("qw0-gap-reduction"))throw new AssertionError("Unexpected open order after reduction submission");openSell=true;
        }
        if(!openSell)throw new AssertionError("Reduction terminated without fill: new strategy action requires full gate");
        decisions.add(Map.of("at",at,"seq",seq,"reason","RESTING_REDUCTION"));
      }
      if(gap)break;
    }
    if(!hedged||(!gap&&!stoppedOnReductionFill)||fills.isEmpty()||(!stoppedOnReductionFill&&(seen.size()!=162||fills.size()!=1)))throw new AssertionError("Incomplete bounded reduction gate");
    BigDecimal remaining=new BigDecimal("5");for(var f:fills)if(!f.buy())remaining=remaining.subtract(f.size());
    if(remaining.signum()<0)throw new AssertionError("Reduction oversold original allocated inventory");
    var out=new LinkedHashMap<String,Object>();out.put("scope","BOUNDED_ACTIVE_REDUCTION_UNTIL_FIRST_NEW_FILL_OR_GAP_NOT_ACCOUNT");out.put("originalSequence",243583);
    out.put("consumedOriginalGroups",seen.size());out.put("decisions",decisions);out.put("hedgeDecision",hedge);out.put("diagnostics",e.diagnostics());out.put("modelAllocations",fills);
    out.put("actualComponentAllocationDiagnostics",e.settlementDiagnostics());out.put("firstScopedGapMs",manifest.path("horizonMs").asLong());out.put("pendingTakerCanceledByGap",pendingTakerDue>=0);
    out.put("remainingUnhedgedShares",remaining);out.put("stoppedOnFirstReductionAllocation",stoppedOnReductionFill);
    out.put("stopOriginalSequence",stopSeq);out.put("stopEventIndex",stopEvent);out.put("firstGapActuallyProcessed",gap);
    out.put("postReductionFillStrategyNotProcessed",stoppedOnReductionFill);out.put("componentPriceRounding","BUY_UP_SELL_DOWN_28");
    out.put("completeInputGroups",162);out.put("accountRiskAndOtherMarketsOmitted",true);out.put("postGapAndResolutionOmitted",true);
    out.put("actualBotFillsCreated",0);out.put("candidateAccountSimulated",false);out.put("netPnlRecomputed",false);out.put("independentPaperQualificationAllowed",false);out.put("liveAllowed",false);
    Files.writeString(Path.of(args[3]),M.writerWithDefaultPrettyPrinter().writeValueAsString(out)+"\n");
  }
}
