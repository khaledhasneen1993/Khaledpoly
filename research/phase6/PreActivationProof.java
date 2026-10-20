package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;

/** Actual643 conserved component tuples in SYNTHETIC pending-order/timestamp contexts. */
public final class PreActivationProof {
  static final ObjectMapper M=NativeReplaySupport.M;
  static int cases,continuations,futureFills;
  static void check(boolean yes,String why){if(!yes)throw new AssertionError(why);}
  static void rejects(Runnable action){try{action.run();}catch(IllegalStateException expected){return;}throw new AssertionError("Unsafe temporal witness accepted");}
  static JsonNode node(Object x){return M.valueToTree(x);}
  static void book(PaperMatchingEngine m,String token,BigDecimal bid,long at){
    var ask=bid.add(BigDecimal.ONE).divide(new BigDecimal("2"));
    m.accept("BOOK",at,node(Map.of("token",token,"sourceMs",at,"bids",List.of(Map.of("price",bid,"size","100")),"asks",List.of(Map.of("price",ask,"size","100")))));
  }
  static SettlementReplayLabels.Binding at(SettlementReplayLabels.Binding b,long at,long source,boolean distinct){
    var parts=b.portions().stream().map(p->new SettlementReplayLabels.Portion(p.identity()+(distinct?":SYNTHETIC_DISTINCT_FUTURE":""),p.token(),p.buy(),p.price(),p.quantity())).toList();
    return new SettlementReplayLabels.Binding(b.seq(),b.index(),at,source,b.tradeHash(),b.token(),b.side(),b.price(),b.size(),b.pair(),parts);
  }
  static PaperMatchingEngine[] setup(SettlementReplayLabels.Binding b){
    var p=b.portions().stream().filter(SettlementReplayLabels.Portion::buy).findFirst().orElse(b.portions().get(0));
    var pair=new PaperMatchingEngine[]{NoOrderDifferentialProbe.matcher(),NoOrderDifferentialProbe.matcher()};long start=b.at();
    for(var m:pair){for(String token:b.pair())book(m,token,token.equals(p.token())?p.price():new BigDecimal(".1"),start-2);
      NoOrderDifferentialProbe.order(m,p.token(),true,p.price(),start);}
    return pair;
  }
  static void differential(SettlementReplayLabels.Binding b,JsonNode original,int delay,boolean latest)throws Exception {
    var ms=setup(b);long arrival=b.at()+delay,source=latest?arrival:b.at()-1;
    var trade=(com.fasterxml.jackson.databind.node.ObjectNode)original.deepCopy();trade.put("sourceMs",source);
    for(var m:ms)check(m.researchPreActivationBuys(arrival,source).size()==1,"Safe pending fixture rejected");
    var left=ms[0].acceptSettlement(arrival,trade,at(b,arrival,source,false));var right=ms[1].accept("TICK",arrival,trade);
    check(left.equals(right)&&left.fills().isEmpty()&&NoOrderDifferentialProbe.execution(ms[0]).equals(NoOrderDifferentialProbe.execution(ms[1])),"Pre-activation execution differs");cases++;
    for(var m:ms)m.accept("TICK",b.at()+250,node(Map.of()));
    for(var m:ms)check(((BigDecimal)m.diagnostics().get(0).get("initialQueueAhead")).compareTo(new BigDecimal("200"))==0,"Displayed100 times queue2 was not preserved");
    check(NoOrderDifferentialProbe.execution(ms[0]).equals(NoOrderDifferentialProbe.execution(ms[1])),"Actual queue/activation continuation changed");
    for(var m:ms)rejects(()->m.researchPreActivationBuys(b.at()+250,b.at()+249));
    long future=b.at()+251;trade.put("sourceMs",future);
    left=ms[0].acceptSettlement(future,trade,at(b,future,future,true));right=ms[1].acceptSettlement(future,trade,at(b,future,future,true));
    check(left.equals(right)&&NoOrderDifferentialProbe.execution(ms[0]).equals(NoOrderDifferentialProbe.execution(ms[1])),"Distinct future queue/fill continuation differs");continuations++;futureFills+=left.fills().size();
  }
  static final List<String> guards=new ArrayList<>();
  interface Change{void apply(AtomicNoOrderGuardProbe.Fixture f)throws Exception;}
  static void waiting(AtomicNoOrderGuardProbe.Fixture f)throws Exception {
    NoOrderDifferentialProbe.book(f.matcher,"a",1000,1000);NoOrderDifferentialProbe.order(f.matcher,"a",true,new BigDecimal(".4"),1001);
    f.ledger.reserve("SYNTHETIC-ORDER","a",true,new BigDecimal(".4"),new BigDecimal("5"));
  }
  static void deny(Path out,String name,long at,long source,Change change)throws Exception {
    try(var f=new AtomicNoOrderGuardProbe.Fixture(out.resolve(name))){waiting(f);change.apply(f);var state=f.ledger.snapshot();var matcher=NoOrderDifferentialProbe.freeze(f.matcher);
      rejects(()->f.session.withResearchUnfillableWitness(at,source,w->{throw new AssertionError("Unsafe callback entered");}));
      check(state.equals(f.ledger.snapshot())&&matcher.equals(NoOrderDifferentialProbe.freeze(f.matcher)),"Refusal changed canonical state");guards.add(name);}
  }
  @SuppressWarnings("unchecked")
  static void guardProof(Path out)throws Exception {
    Files.createDirectory(out);
    try(var f=new AtomicNoOrderGuardProbe.Fixture(out.resolve("safe"))){waiting(f);var escaped=new ResearchSession.NoOrderWitness[1];
      f.session.withResearchUnfillableWitness(1021,1021,w->{w.requireValid();escaped[0]=w;return null;});rejects(escaped[0]::requireValid);
      f.session.withResearchUnfillableWitness(1250,1250,w->{w.requireValid();return null;});
      check(f.matcher.diagnostics().get(0).get("activationDueMs").equals(1251L),"Latency changed");
    }
    deny(out,"ACTIVATION_DUE_EQUAL",1251,1251,f->{});deny(out,"ACTIVATION_PAST_DUE",1252,1252,f->{});
    deny(out,"ACTIVE",1252,1252,f->f.matcher.accept("TICK",1251,node(Map.of())));
    deny(out,"SELL_PENDING",1021,1021,f->f.matcher.accept("ORDER",1002,node(Map.of("id","SYNTHETIC-SELL","token","b","side","SELL","price",".4","size","5"))));
    deny(out,"CANCEL_PENDING",1021,1021,f->f.matcher.accept("CANCEL",1002,node(Map.of("id","SYNTHETIC-ORDER"))));
    deny(out,"CANCEL_DUE",1252,1252,f->f.matcher.accept("CANCEL",1002,node(Map.of("id","SYNTHETIC-ORDER"))));
    deny(out,"SOURCE_FUTURE",1021,1022,f->{});deny(out,"SOURCE_NEGATIVE",1021,-1,f->{});
    deny(out,"CLOCK_REGRESSION",1000,1000,f->{});
    deny(out,"RESERVATION_MISSING",1021,1021,f->f.ledger.cancel("SYNTHETIC-ORDER"));
    deny(out,"ORPHAN_RESERVATION",1021,1021,f->f.ledger.reserve("orphan","a",true,new BigDecimal(".4"),BigDecimal.ONE));
    deny(out,"RESERVATION_MISMATCH",1021,1021,f->{f.ledger.cancel("SYNTHETIC-ORDER");f.ledger.reserve("wrong","b",true,new BigDecimal(".3"),BigDecimal.ONE);});
    deny(out,"HOLDING",1021,1021,f->f.ledger.fill("SYNTHETIC-fill","SYNTHETIC-ORDER",BigDecimal.ONE,new BigDecimal(".4"),BigDecimal.ZERO));
    deny(out,"PENDING_FOK",1021,1021,f->((List<Object>)AtomicNoOrderGuardProbe.field(f.session,"pending")).add(null));
    deny(out,"UNHEDGED_TIMER",1021,1021,f->((Map<String,Long>)AtomicNoOrderGuardProbe.field(f.session,"unhedged")).put("a",1L));
    deny(out,"SESSION_FAILED",1021,1021,f->AtomicNoOrderGuardProbe.set(f.session,"failed",true));
    deny(out,"ENTRY_STOPPED",1021,1021,f->AtomicNoOrderGuardProbe.set(f.session,"entryStopped",true));
    deny(out,"HALTED",1021,1021,f->f.ledger.halt());deny(out,"PERSISTENCE_FAILED",1021,1021,f->AtomicNoOrderGuardProbe.set(f.ledger,"failed",true));
    deny(out,"CHECKPOINT_CLOSED",1021,1021,f->f.checkpoint.close());deny(out,"LEDGER_CLOSED",1021,1021,f->f.ledger.close());
    deny(out,"EXTERNAL_MODE",1021,1021,f->AtomicNoOrderGuardProbe.set(f.session,"externalMode",true));
    deny(out,"RECOVERED_CHECKPOINT",1021,1021,f->AtomicNoOrderGuardProbe.set(f.session,"researchRecoveredCheckpoint",true));
  }
  public static void main(String[] args)throws Exception {
    Path out=Path.of(args[2]);Files.createDirectory(out);JsonNode source=M.readTree(Files.readString(Path.of(args[1])));
    var pool=new ConservedReceiptPool(M.readTree(Files.readString(Path.of(args[0]))),M);SettlementReplayLabels.Binding repeated=null;JsonNode repeatTrade=null;
    check(ConservedReceiptPool.hash(Files.readString(Path.of(args[0]))).equals("c41eda69ffe03ed06835a9fac403401f0d68aa3fa92b019bf37d410a212ee231"),"Pool changed");
    check(ConservedReceiptPool.hash(Files.readString(Path.of(args[1]))).equals("27ac545988149c87bdfd4caee963100b7d10eb2808e6a74d82ae4b8321c65423"),"Original preimages changed");
    for(var row:source.path("observations")){
      var b=pool.resolve(row.path("seq").asLong(),row.path("eventIndex").asInt(),row.path("at").asLong(),row.path("data"));
      for(int delay:List.of(0,20,54,249))for(boolean latest:List.of(false,true))differential(b,row.path("data"),delay,latest);
      if(repeated==null&&b.portions().stream().anyMatch(p->p.buy()&&p.quantity().compareTo(new BigDecimal("200"))>0)){repeated=b;repeatTrade=row.path("data");}
    }
    pool.requireConsumed();check(cases==5144&&continuations==5144&&futureFills>0&&repeated!=null,"Incomplete proof contexts");
    var ms=setup(repeated);var trade=(com.fasterxml.jackson.databind.node.ObjectNode)repeatTrade.deepCopy();trade.put("sourceMs",repeated.at()-1);
    ms[0].acceptSettlement(repeated.at(),trade,at(repeated,repeated.at(),repeated.at()-1,false));ms[1].accept("TICK",repeated.at(),trade);
    for(var m:ms)m.accept("TICK",repeated.at()+250,node(Map.of()));trade.put("sourceMs",repeated.at()+251);
    check(!ms[0].acceptSettlement(repeated.at()+251,trade,at(repeated,repeated.at()+251,repeated.at()+251,false))
        .equals(ms[1].acceptSettlement(repeated.at()+251,trade,at(repeated,repeated.at()+251,repeated.at()+251,false))),"Required repeated component counterexample absent");
    guardProof(out.resolve("guards"));var result=new LinkedHashMap<String,Object>();result.put("scope","SYNTHETIC_PRE_ACTIVATION_CONTEXTS_OVER_ACTUAL643_COMPONENTS_NOT_MARKET");
    result.put("actualIdentities",643);result.put("pendingDifferentials",cases);result.put("distinctFutureContinuations",continuations);result.put("syntheticFutureFillEvents",futureFills);
    result.put("sourceTimeContexts",List.of("BEFORE_SUBMIT","LATEST_AT_ARRIVAL"));result.put("pendingAgeContextsMs",List.of(0,20,54,249));result.put("activationMsUnchanged",250);result.put("queueMultiplierUnchanged",2);
    result.put("rejectionGuards",guards);result.put("allNonSettlementPrivateMatchingFieldsCompared",true);result.put("repeatedComponentFutureDivergenceVerified",true);result.put("oldEmptyOrderGuardUnchanged",true);
    for(String flag:List.of("fullMatchingStateEquivalent","marketNetPnlRecomputed","originalTapeReplayed","independentPaperQualificationAllowed","liveAllowed"))result.put(flag,false);
    M.writerWithDefaultPrettyPrinter().writeValue(out.resolve("preactivation-proof.json").toFile(),result);System.out.println(M.writeValueAsString(result));
  }
}
