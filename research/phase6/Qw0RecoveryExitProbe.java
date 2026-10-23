package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.io.*;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Conditional prior-model inventory; stop at FIRST new maker allocation or atomic taker FOK. */
public final class Qw0RecoveryExitProbe {
  static final ObjectMapper M=Qw0CausalProbe.M;
  static JsonNode node(Object o){return M.valueToTree(o);}
  static BigDecimal d(JsonNode n){return Qw0CausalProbe.dec(n);}
  record Planned(String token,boolean buy,long due,BigDecimal limit,String purpose) {}
  static boolean fresh(JsonNode b,long at){return b!=null&&!b.path("bids").isEmpty()&&!b.path("asks").isEmpty()&&0<=at-b.path("sourceMs").asLong()&&at-b.path("sourceMs").asLong()<=2000;}
  static BigDecimal best(JsonNode b,String side,boolean high){return Qw0ActiveReductionProbe.best(b,side,high);}
  static List<Map<String,Object>> open(PaperMatchingEngine engine){return engine.diagnostics().stream().filter(x->x.get("terminalMs")==null).toList();}
  static boolean overdue(long now,long first,long limit){return now-first>=limit;}
  public static void main(String[] args)throws Exception {
    if(args.length==1&&args[0].equals("--self-test")) {
      if(overdue(29999,0,30000)||!overdue(30000,0,30000))throw new AssertionError("Unhedged deadline boundary differs");
      var levels=new TreeMap<BigDecimal,BigDecimal>();levels.put(new BigDecimal(".5"),new BigDecimal("2"));levels.put(new BigDecimal(".51"),new BigDecimal("3"));
      var f=new FeeModel(new BigDecimal(".07"),1);var fill=DepthExecution.sweep(levels,true,new BigDecimal("5"),new BigDecimal(".51"),f);
      if(fill.size().compareTo(new BigDecimal("5"))!=0||fill.legs().size()!=2||fill.fee().compareTo(new BigDecimal(".08748"))!=0)throw new AssertionError("Actual multi-level FOK fee differs");
      boolean rejected=false;try{DepthExecution.sweep(levels,true,new BigDecimal("6"),new BigDecimal(".51"),f);}catch(IllegalStateException expected){rejected=true;}
      if(!rejected)throw new AssertionError("No imaginary depth allowed");
      System.out.println("2 risk-clock and3 actual multi-level FOK/fee/depth assertions passed");return;
    }
    if(args.length!=3)throw new IllegalArgumentException("original.records.gz frozen-input report");
    var input=M.readTree(Files.readString(Path.of(args[1])));var cfg=input.path("config");JsonNode market=input.path("market");
    if(!input.path("seedFromPriorNativeModelNotActualBotInventory").asBoolean()||!input.path("stopImmediatelyOnFirstNewAllocation").asBoolean())throw new AssertionError("Wrong conditional gate contract");
    long start=input.path("startMs").asLong(),horizon=input.path("horizonMs").asLong(),first=input.path("firstModelAllocationMs").asLong(),next=input.path("nextDecisionMs").asLong();
    if(start-first<=5000||next!=1792269761068L)throw new AssertionError("Original wait/next-callback proof missing");
    String lead=market.path("first").asText(),other=market.path("second").asText();Set<String> pair=Set.of(lead,other);
    BigDecimal quantity=d(input.path("initialQuantity")),basis=d(input.path("initialBasisPerShare")),lossBudget=d(input.path("initialUnspentExitLossBudget"));
    if(quantity.compareTo(new BigDecimal("5"))!=0||basis.compareTo(new BigDecimal(".48"))!=0)throw new AssertionError("Changed prior model seed");
    var labels=new HashMap<String,JsonNode>();for(var b:input.path("bindings"))if(labels.putIfAbsent(b.path("seq").asLong()+":"+b.path("eventIndex").asInt(),b)!=null)throw new AssertionError("Duplicate original group");
    if(labels.size()!=451)throw new AssertionError("Complete451 source labels required");
    var engine=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));var books=new HashMap<String,JsonNode>();
    var decisions=new ArrayList<Object>();var allocations=new ArrayList<Object>();var seen=new HashSet<String>();var cancelRequested=new HashSet<String>();
    Planned pending=null;long sequence=0,lastSeq=-1,lastAt=-1;String stop="FIXED_HORIZON_WITH_UNRESOLVED_INVENTORY";int stopEvent=-1;boolean stopped=false;
    try(var reader=new BufferedReader(new InputStreamReader(new GZIPInputStream(Files.newInputStream(Path.of(args[0])))))) {
      replay:for(String line;(line=reader.readLine())!=null;) {
        var row=M.readTree(line).path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();if(at>horizon)break;
        lastSeq=seq;lastAt=at;String kind=row.path("kind").asText().substring(9);var events=kind.equals("FRAME")?row.path("data").path("events"):node(List.of(Map.of("kind",kind,"data",row.path("data"))));int ix=0;
        for(var event:events) {
          String k=event.path("kind").asText();var v=event.path("data");var binding=labels.get(seq+":"+ix);
          if(k.equals("META")) {
            if(v.path("condition").asText().equals(market.path("condition").asText())) {
              if(!v.path("first").asText().equals(lead)||!v.path("second").asText().equals(other)
                  ||v.path("startMs").asLong()!=market.path("startMs").asLong()||v.path("endMs").asLong()!=market.path("endMs").asLong()
                  ||v.path("negativeRisk").asBoolean()!=market.path("negativeRisk").asBoolean()||v.path("observedMs").asLong()>at)throw new AssertionError("Changed original pair metadata");market=v;
              if(!market.path("accepting").asBoolean()) {
                for(String token:pair)Qw0CausalProbe.noFill(engine.accept("CLOSE",at,node(Map.of("token",token,"reason","MARKET_CLOSED_OR_RESOLVED"))));books.clear();pending=null;
              }
            }
          } else if(k.equals("BOOK")) {
            Qw0CausalProbe.noFill(engine.accept(k,at,v));String token=v.path("token").asText();long source=v.path("sourceMs").asLong(-1);var old=books.get(token);
            if(pair.contains(token)){if(source<0||source>at||at-source>2000||old!=null&&source<old.path("sourceMs").asLong())books.remove(token);else books.put(token,v);}
          } else if(k.equals("TRADE")&&binding!=null) {
            String key=seq+":"+ix;if(!seen.add(key))throw new AssertionError("Repeated original observation");
            var update=engine.acceptSettlement(at,v,Qw0ActiveReductionProbe.binding(binding,v,seq,ix,at,pair));
            if(!update.fills().isEmpty()) {
              for(var f:update.fills())if(f.buy()||!f.token().equals(lead)||f.size().compareTo(quantity)>0)throw new AssertionError("Unexpected recovery inventory change");
              if(update.fills().stream().map(PaperMatchingEngine.Fill::size).reduce(BigDecimal.ZERO,BigDecimal::add).compareTo(quantity)>0)throw new AssertionError("Recovery allocation oversold conditional inventory");
              allocations.addAll(update.fills());stop="FIRST_NEW_MAKER_ALLOCATION_STOP_BEFORE_REMAINING_FRAME_OR_STRATEGY";stopEvent=ix;stopped=true;break replay;
            }
          } else if(k.equals("TRADE")||k.equals("TICK")) {
            if(k.equals("TRADE")&&at>start&&pair.contains(v.path("token").asText()))throw new AssertionError("Unknown original pair print");
            Qw0CausalProbe.noFill(engine.accept("TICK",at,v));
          } else if(k.equals("GAP")||k.equals("FEED_ERROR")) {
            var affected=new HashSet<String>();v.path("tokens").forEach(t->affected.add(t.asText()));if(v.has("token"))affected.add(v.path("token").asText());
            if(affected.isEmpty()||affected.stream().anyMatch(pair::contains)){Qw0CausalProbe.noFill(engine.accept("GAP",at,node(Map.of("tokens",pair,"reason",v.path("reason").asText("unknown")))));books.clear();pending=null;cancelRequested.clear();}
            else Qw0CausalProbe.noFill(engine.accept("GAP",at,v));
          } else throw new AssertionError("Unmodelled original action "+k);
          ix++;
        }
        if(at<start||!Qw0ActiveReductionProbe.advances(kind,events))continue;
        if(pending!=null&&at>=pending.due()) {
          var p=pending;pending=null;var book=books.get(p.token());
          if(!fresh(book,at)||at>=market.path("endMs").asLong()||at-market.path("observedMs").asLong()>cfg.path("metadataMaxAgeMs").asLong()){decisions.add(Map.of("at",at,"seq",seq,"reason","TAKER_DATA_REJECT"));}
          else if(open(engine).isEmpty()&&quantity.compareTo(d(market.path("minSize")))>=0) {
            var depth=new TreeMap<BigDecimal,BigDecimal>();for(var l:book.path(p.buy()?"asks":"bids"))depth.put(d(l.path("price")),d(l.path("size")));
            var fee=new FeeModel(d(market.path("feeRate")).multiply(d(cfg.path("feeMultiplier"))),market.path("feeExponent").asInt());DepthExecution.Result result=null;
            try{result=DepthExecution.sweep(depth,p.buy(),quantity,p.limit(),fee);}catch(IllegalStateException rejected){decisions.add(Map.of("at",at,"seq",seq,"reason","TAKER_FOK_REJECT"));}
            if(result!=null) {
              var seedCost=basis.multiply(quantity);var pnl=p.buy()?quantity.subtract(seedCost).subtract(result.notional()).subtract(result.fee()).subtract(d(cfg.path("mergeCost"))):result.notional().subtract(result.fee()).subtract(seedCost);
              if(p.purpose().equals("POSITIVE_EDGE_COMPLETION")&&pnl.compareTo(d(cfg.path("minimumEdge")).multiply(quantity))<0)decisions.add(Map.of("at",at,"seq",seq,"reason","TAKER_NET_EDGE"));
              else if(pnl.negate().max(BigDecimal.ZERO).compareTo(lossBudget)>0)decisions.add(Map.of("at",at,"seq",seq,"reason","EXIT_LOSS_CAP"));
              else if(p.buy()&&p.limit().multiply(quantity).add(result.fee()).compareTo(d(cfg.path("initialCash")).subtract(seedCost))>0)throw new AssertionError("Insufficient conditional cash; no funding fabrication");
              else {allocations.add(Map.of("at",at,"seq",seq,"token",p.token(),"buy",p.buy(),"quantity",quantity,"purpose",p.purpose(),"result",result));stop="FIRST_NEW_ATOMIC_TAKER_FOK_STOP_BEFORE_MERGE_OR_STRATEGY";stopped=true;break;}
            }
          }
        }
        if(at<next)continue;next=at+cfg.path("decisionMillis").asLong();
        var active=open(engine);String unavailable=at<market.path("startMs").asLong()||at>=market.path("endMs").asLong()?"OUTSIDE_MARKET":!fresh(books.get(lead),at)||!fresh(books.get(other),at)?"BOOK_UNAVAILABLE":at-market.path("observedMs").asLong()>cfg.path("metadataMaxAgeMs").asLong()?"METADATA_STALE":!market.path("accepting").asBoolean()?"MARKET_UNAVAILABLE":null;
        boolean overdue=overdue(at,first,cfg.path("unhedgedMs").asLong())||quantity.compareTo(d(cfg.path("maxUnhedged")))>=0;
        if(unavailable!=null||!active.isEmpty()) {
          if(unavailable==null&&!overdue){decisions.add(Map.of("at",at,"seq",seq,"reason","RESTING_REDUCTION"));continue;}
          for(var o:active)if(cancelRequested.add(o.get("id").toString()))engine.accept("CANCEL",at,node(Map.of("id",o.get("id"),"reason",unavailable==null?"CANCEL_BEFORE_RISK_EXIT":unavailable)));
          decisions.add(Map.of("at",at,"seq",seq,"reason",unavailable==null?"CANCEL_BEFORE_EXIT":unavailable));continue;
        }
        if(pending!=null)continue;
        var lb=books.get(lead);var ob=books.get(other);var tick=d(market.path("tick"));var bid=best(lb,"bids",true);var ask=best(lb,"asks",false);var opposite=best(ob,"asks",false);
        var fee=new FeeModel(d(market.path("feeRate")).multiply(d(cfg.path("feeMultiplier"))),market.path("feeExponent").asInt());
        var choice=PairPolicy.hedge(basis,opposite,bid,fee.fee(BigDecimal.ONE,opposite,false).add(d(cfg.path("mergeCost")).divide(quantity,18,RoundingMode.UP)),fee.fee(BigDecimal.ONE,bid,false),d(cfg.path("minimumEdge")),overdue);
        if(!overdue&&!choice.action().equals("COMPLETE")) {
          var price=ask.subtract(tick).max(bid.add(tick));
          if(price.compareTo(BigDecimal.ONE)>=0||quantity.compareTo(d(market.path("minSize")))<0||basis.subtract(price).multiply(quantity).max(BigDecimal.ZERO).compareTo(lossBudget)>0){decisions.add(Map.of("at",at,"seq",seq,"reason","REDUCTION_CONSTRAINT"));continue;}
          String id="qw0-recovery-"+(++sequence);Qw0CausalProbe.noFill(engine.accept("ORDER",at,node(Map.of("id",id,"token",lead,"side","SELL","price",price,"size",quantity))));
          decisions.add(Map.of("at",at,"seq",seq,"reason","MAKER_REDUCTION","id",id,"price",price,"choice",choice));
        } else {
          boolean buy=choice.action().endsWith("COMPLETE");var book=buy?ob:lb;var limit=buy?best(book,"asks",false).add(tick.multiply(new BigDecimal("3"))).min(BigDecimal.ONE.subtract(tick)):best(book,"bids",true).subtract(tick.multiply(new BigDecimal("3"))).max(tick);
          pending=new Planned(buy?other:lead,buy,at+250,limit,overdue?"RISK_REDUCTION":"POSITIVE_EDGE_COMPLETION");decisions.add(Map.of("at",at,"seq",seq,"reason","TAKER_PENDING","pending",pending,"choice",choice));
        }
      }
    }
    var out=new LinkedHashMap<String,Object>();out.put("scope",input.path("scope").asText());out.put("stopReason",stop);out.put("stopAt",lastAt);out.put("stopSequence",lastSeq);out.put("stopEventIndex",stopEvent);
    out.put("stoppedOnNewAllocation",stopped);out.put("modelExitAllocations",allocations);out.put("decisions",decisions);out.put("diagnostics",engine.diagnostics());out.put("componentAllocationDiagnostics",engine.settlementDiagnostics());out.put("consumedOriginalGroups",seen.size());out.put("completeInputGroups",451);
    out.put("conditionalInitialQuantity",quantity);out.put("postAllocationInventoryAndMergeNotProcessed",stopped);out.put("accountRiskAssumedAvailable",true);out.put("otherMarketsAndFullAccountOmitted",true);out.put("actualBotFillsCreated",0);out.put("candidateAccountSimulated",false);out.put("netPnlRecomputed",false);out.put("independentPaperQualificationAllowed",false);out.put("liveAllowed",false);
    Files.writeString(Path.of(args[2]),M.writerWithDefaultPrettyPrinter().writeValueAsString(out)+"\n");
  }
}
