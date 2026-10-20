package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;

/** PROOF ONLY: reflected temporal predicate is NOT installed in any runtime guard. */
public final class SourceLagDifferentialProof {
  static final ObjectMapper M=NativeReplaySupport.M;
  static final List<String> CONTEXTS=List.of("ACTIVE_SOURCE_MINUS66","ACTIVE_SOURCE_EQUAL","DUE_AT_ARRIVAL_EQUAL",
      "DELAYED_ACTIVATION_EQUAL","TWO_ORDERS_OLDEST_CUTOFF","CANCEL_DUE_ACTIVATION_TIE","CANCEL_PENDING","STALE_ACTIVE_BOOK");
  static int cases,continuations,futureFills;static final List<String> guards=new ArrayList<>();
  static void check(boolean x,String why){if(!x)throw new AssertionError(why);}
  static JsonNode node(Object x){return M.valueToTree(x);}
  static Object field(Object x,String name)throws Exception{return NoOrderDifferentialProbe.field(x,name);}
  static void order(PaperMatchingEngine m,String id,String token,BigDecimal price,long at){
    m.accept("ORDER",at,node(Map.of("id",id,"token",token,"side","BUY","price",price,"size","5")));
  }
  /** Proposed MATH predicate only. Flat/persistence/ledger/atomic integration NOT proved here. */
  static boolean proofPredicate(PaperMatchingEngine m,long arrival,long source)throws Exception {
    if(source<0||source>arrival||arrival<(long)field(m,"now"))return false;
    var orders=(Map<?,?>)field(m,"orders");if(orders.isEmpty())return false;
    for(var o:orders.values()){
      if(!(boolean)field(o,"buy")||(long)field(o,"cancel")!=Long.MAX_VALUE||((BigDecimal)field(o,"remaining")).signum()<=0)return false;
      // Pending orders activate no earlier than this event. ALREADY-active orders use ACTUAL activated, not nominal due.
      if((boolean)field(o,"active")&&source>(long)field(o,"activated"))return false;
    }
    return true;
  }
  static void same(PaperMatchingEngine[] ms,PaperMatchingEngine.Update left,PaperMatchingEngine.Update right,String why)throws Exception {
    check(left.equals(right)&&NoOrderDifferentialProbe.execution(ms[0]).equals(NoOrderDifferentialProbe.execution(ms[1])),why);
  }
  static void differential(SettlementReplayLabels.Binding b,JsonNode original,String context)throws Exception {
    var ms=PreActivationProof.setup(b);long start=b.at(),arrival=start+320,source=start+250;
    switch(context){
      case "ACTIVE_SOURCE_MINUS66" -> source=start+184;
      case "ACTIVE_SOURCE_EQUAL" -> {}
      case "DUE_AT_ARRIVAL_EQUAL" -> arrival=start+250;
      case "DELAYED_ACTIVATION_EQUAL" -> source=arrival;
      case "TWO_ORDERS_OLDEST_CUTOFF" -> {arrival=start+501;var p=b.portions().stream().filter(SettlementReplayLabels.Portion::buy).findFirst().orElse(b.portions().get(0));
        for(var m:ms){m.accept("TICK",start+250,node(Map.of()));order(m,"SYNTHETIC-SECOND",p.token(),p.price(),start+251);m.accept("TICK",start+501,node(Map.of()));}}
      case "CANCEL_DUE_ACTIVATION_TIE" -> {arrival=start+250;for(var m:ms)m.accept("CANCEL",start,node(Map.of("id","SYNTHETIC-ORDER")));}
      case "CANCEL_PENDING" -> {for(var m:ms){m.accept("TICK",start+250,node(Map.of()));m.accept("CANCEL",start+251,node(Map.of("id","SYNTHETIC-ORDER")));}}
      case "STALE_ACTIVE_BOOK" -> arrival=start+3001;
      default -> throw new AssertionError(context);
    }
    if(!Set.of("DUE_AT_ARRIVAL_EQUAL","DELAYED_ACTIVATION_EQUAL","TWO_ORDERS_OLDEST_CUTOFF","CANCEL_DUE_ACTIVATION_TIE","CANCEL_PENDING").contains(context))
      for(var m:ms)m.accept("TICK",start+250,node(Map.of()));
    for(var m:ms){
      boolean expected=!context.startsWith("CANCEL");check(proofPredicate(m,arrival,source)==expected,"Predicate scope changed "+context);
      if(context.equals("TWO_ORDERS_OLDEST_CUTOFF"))check(((BigDecimal)m.diagnostics().get(1).get("initialQueueAhead")).compareTo(new BigDecimal("205"))==0,"Lost earlier own-order queue");
    }
    var trade=(ObjectNode)original.deepCopy();trade.put("sourceMs",source);
    var left=ms[0].acceptSettlement(arrival,trade,PreActivationProof.at(b,arrival,source,false));var right=ms[1].accept("TICK",arrival,trade);
    same(ms,left,right,"Source-lag execution differs "+context);check(left.fills().isEmpty(),"Early source filled");cases++;
    if(context.equals("CANCEL_DUE_ACTIVATION_TIE"))check(left.terminal().size()==1&&ms[0].diagnostics().get(0).get("activatedMs")==null,"Cancel lost activation tie");
    if(context.equals("STALE_ACTIVE_BOOK"))check(left.reasons().containsValue("STALE_BOOK"),"Stale book not canonically canceled");
    if(!context.startsWith("CANCEL")&&!context.equals("STALE_ACTIVE_BOOK"))check(((BigDecimal)ms[0].diagnostics().get(0).get("initialQueueAhead")).compareTo(new BigDecimal("200"))==0,"Activation queue changed");
    // Same distinct future actual component quantities, but synthetic identity/time context, never MARKET fills.
    long future=arrival+1;for(var m:ms)for(String token:b.pair())PreActivationProof.book(m,token,new BigDecimal(".01"),future);
    trade.put("sourceMs",future);left=ms[0].acceptSettlement(future,trade,PreActivationProof.at(b,future,future,true));right=ms[1].acceptSettlement(future,trade,PreActivationProof.at(b,future,future,true));
    same(ms,left,right,"Distinct future queue/fill differs "+context);continuations++;futureFills+=left.fills().size();
  }
  static void reject(String name,PaperMatchingEngine m,long arrival,long source)throws Exception {
    var before=NoOrderDifferentialProbe.freeze(m);check(!proofPredicate(m,arrival,source),"Unsafe predicate accepted "+name);
    check(before.equals(NoOrderDifferentialProbe.freeze(m)),"Predicate mutated matcher");guards.add(name);
  }
  static Map<String,Object> counterexamples(SettlementReplayLabels.Binding b,JsonNode original)throws Exception {
    long start=b.at();var ms=PreActivationProof.setup(b);for(var m:ms)m.accept("TICK",start+250,node(Map.of()));
    reject("SOURCE_AFTER_ACTUAL_ACTIVATION",ms[0],start+320,start+251);
    reject("FUTURE_SOURCE",ms[0],start+320,start+321);reject("NEGATIVE_SOURCE",ms[0],start+320,-1);reject("CLOCK_REGRESSION",ms[0],start+249,start+249);
    var trade=(ObjectNode)original.deepCopy();trade.put("sourceMs",start+251);
    var filled=ms[0].acceptSettlement(start+320,trade,PreActivationProof.at(b,start+320,start+251,false));var skipped=ms[1].accept("TICK",start+320,trade);
    check(!filled.equals(skipped)&&!filled.fills().isEmpty(),"Post-activation +1ms unsafe counterexample absent");
    // A maximum/newest activation cutoff is UNSAFE: the older order can already consume the component.
    ms=PreActivationProof.setup(b);var p=b.portions().stream().filter(x->x.buy()&&x.quantity().compareTo(new BigDecimal("200"))>0).findFirst().orElseThrow();
    for(var m:ms){m.accept("TICK",start+250,node(Map.of()));order(m,"SYNTHETIC-SECOND",p.token(),p.price(),start+251);m.accept("TICK",start+501,node(Map.of()));}
    reject("OLDER_ORDER_ELIGIBLE_DESPITE_NEWER_ORDER",ms[0],start+510,start+300);trade.put("sourceMs",start+300);
    filled=ms[0].acceptSettlement(start+510,trade,PreActivationProof.at(b,start+510,start+300,false));skipped=ms[1].accept("TICK",start+510,trade);
    check(!filled.equals(skipped)&&!filled.fills().isEmpty(),"Newest-order cutoff counterexample absent");
    ms=PreActivationProof.setup(b);for(var m:ms)m.accept("CANCEL",start,node(Map.of("id","SYNTHETIC-ORDER")));reject("CANCEL_PENDING",ms[0],start+249,start+249);reject("CANCEL_DUE",ms[0],start+250,start+250);
    ms=PreActivationProof.setup(b);ms[0].accept("ORDER",start,node(Map.of("id","SYNTHETIC-SELL","token",p.token(),"side","SELL","price",".99","size","5")));reject("SELL_EXPOSURE",ms[0],start+10,start+10);
    reject("EMPTY_NOT_TEMPORAL_EXPOSURE",NoOrderDifferentialProbe.matcher(),start,start);
    // Reusing a known component after omitting it changes future execution; global uniqueness is mandatory.
    ms=PreActivationProof.setup(b);trade.put("sourceMs",start+250);for(var m:ms)m.accept("TICK",start+250,node(Map.of()));
    ms[0].acceptSettlement(start+320,trade,PreActivationProof.at(b,start+320,start+250,false));ms[1].accept("TICK",start+320,trade);
    trade.put("sourceMs",start+321);filled=ms[0].acceptSettlement(start+321,trade,PreActivationProof.at(b,start+321,start+321,false));skipped=ms[1].acceptSettlement(start+321,trade,PreActivationProof.at(b,start+321,start+321,false));
    check(!filled.equals(skipped)&&!skipped.fills().isEmpty(),"Repeated component future divergence absent");
    return Map.of("afterActivationOneMillisecondProducesSyntheticFill",true,"newestOrderCutoffWouldMissOlderEligibleOrder",true,"repeatedComponentFutureDivergenceVerified",true);
  }
  public static void main(String[] args)throws Exception {
    Path out=Path.of(args[2]);Files.createDirectory(out);JsonNode identities=M.readTree(Files.readString(Path.of(args[1])));
    check(ConservedReceiptPool.hash(Files.readString(Path.of(args[0]))).equals("c41eda69ffe03ed06835a9fac403401f0d68aa3fa92b019bf37d410a212ee231"),"Pool changed");
    check(ConservedReceiptPool.hash(Files.readString(Path.of(args[1]))).equals("27ac545988149c87bdfd4caee963100b7d10eb2808e6a74d82ae4b8321c65423"),"Source changed");
    var pool=new ConservedReceiptPool(M.readTree(Files.readString(Path.of(args[0]))),M);SettlementReplayLabels.Binding large=null;JsonNode largeTrade=null;
    for(var row:identities.path("observations")){
      var b=pool.resolve(row.path("seq").asLong(),row.path("eventIndex").asInt(),row.path("at").asLong(),row.path("data"));
      for(String context:CONTEXTS)differential(b,row.path("data"),context);
      if(large==null&&b.portions().stream().anyMatch(p->p.buy()&&p.quantity().compareTo(new BigDecimal("200"))>0)){large=b;largeTrade=row.path("data");}
    }
    pool.requireConsumed();check(cases==5144&&continuations==5144&&futureFills>0&&large!=null,"Incomplete source-lag evidence");
    var negatives=counterexamples(large,largeTrade);var result=new LinkedHashMap<String,Object>();result.put("scope","SYNTHETIC_SOURCE_LAG_DIFFERENTIAL_OVER_ACTUAL643_COMPONENTS_NOT_RUNTIME_AUTHORIZATION");
    result.put("originalIdentities",643);result.put("matcherDifferentials",cases);result.put("distinctFutureContinuations",continuations);result.put("syntheticFutureFillEvents",futureFills);result.put("contexts",CONTEXTS);
    result.put("proofPredicateRejections",guards);result.put("counterexamples",negatives);result.put("allNonSettlementPrivateMatchingFieldsCompared",true);result.put("activationMsUnchanged",250);result.put("queueMultiplierUnchanged",2);
    result.put("runtimeRequiresAllOrdersActualActivationCutoff",true);result.put("globalComponentUniquenessStillRequired",true);
    for(String flag:List.of("fullMatchingStateEquivalent","newAtomicSessionGuardImplemented","newRuntimeShortcutEnabled","originalTapeReplayed","completeAccountComparisonPerformed","marketNetPnlRecomputed","independentPaperQualificationAllowed","liveAllowed"))result.put(flag,false);
    M.writerWithDefaultPrettyPrinter().writeValue(out.resolve("source-lag-proof.json").toFile(),result);System.out.println(M.writeValueAsString(result));
  }
}
