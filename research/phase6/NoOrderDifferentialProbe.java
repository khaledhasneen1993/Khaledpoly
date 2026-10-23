package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.lang.reflect.*;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;

/** PROOF ONLY. No runtime method/adapter/fallback is changed or registered. */
public final class NoOrderDifferentialProbe {
  static final ObjectMapper M=NativeReplaySupport.M;
  static final Set<String> EXCLUDED=Set.of("settlementComponents","settlementVenue","settlementAllocated","settlementQueue","settlementUnused");
  static final List<String> rejected=new ArrayList<>();static int cases,futureCases,futureFills;
  static Object field(Object x,String name)throws Exception {var f=x.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(x);}
  static Object freeze(Object x)throws Exception {
    if(x==null||x instanceof String||x instanceof Boolean)return x;
    if(x instanceof Number||x instanceof Enum<?>)return x.getClass().getName()+":"+x;
    if(x instanceof Map<?,?> map){var out=new TreeMap<String,Object>();for(var e:map.entrySet())out.put(String.valueOf(e.getKey()),freeze(e.getValue()));return out;}
    if(x instanceof Set<?> set){var out=new ArrayList<String>();for(var v:set)out.add(M.writeValueAsString(freeze(v)));Collections.sort(out);return out;}
    if(x instanceof Collection<?> list){var out=new ArrayList<Object>();for(var v:list)out.add(freeze(v));return out;}
    var out=new TreeMap<String,Object>();for(var f:x.getClass().getDeclaredFields())if(!Modifier.isStatic(f.getModifiers())&&!f.isSynthetic()){f.setAccessible(true);out.put(f.getName(),freeze(f.get(x)));}return out;
  }
  static Map<String,Object> execution(PaperMatchingEngine matcher)throws Exception {
    var out=new TreeMap<String,Object>();for(var f:PaperMatchingEngine.class.getDeclaredFields())if(!Modifier.isStatic(f.getModifiers())&&!EXCLUDED.contains(f.getName())){f.setAccessible(true);out.put(f.getName(),freeze(f.get(matcher)));}return out;
  }
  static PaperMatchingEngine matcher(){return new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));}
  static JsonNode node(Object x){return M.valueToTree(x);}
  static void book(PaperMatchingEngine m,String token,long at,long source)throws Exception {
    m.accept("BOOK",at,node(Map.of("token",token,"sourceMs",source,"bids",List.of(Map.of("price",".01","size","100")),"asks",List.of(Map.of("price",".99","size","100")))));
  }
  static boolean eligible(PaperMatchingEngine m,AccountLedger.State state,int pending,boolean failed,boolean stopped)throws Exception {
    return ((Map<?,?>)field(m,"orders")).isEmpty()&&pending==0&&!failed&&!stopped&&!state.halted()
        &&state.holdings().values().stream().allMatch(h->h.shares().signum()==0&&h.basis().signum()==0)
        &&state.orders().values().stream().allMatch(o->o.remaining().signum()==0&&Set.of("CANCELED","FILLED","REJECTED").contains(o.status()));
  }
  static void order(PaperMatchingEngine m,String token,boolean buy,BigDecimal price,long at) {
    m.accept("ORDER",at,node(Map.of("id","SYNTHETIC-ORDER","token",token,"side",buy?"BUY":"SELL","price",price,"size","5")));
  }
  static SettlementReplayLabels.Binding future(SettlementReplayLabels.Binding b,long at,boolean distinct) {
    var ps=b.portions().stream().map(p->new SettlementReplayLabels.Portion(p.identity()+(distinct?":SYNTHETIC_DISTINCT_FUTURE":""),p.token(),p.buy(),p.price(),p.quantity())).toList();
    return new SettlementReplayLabels.Binding(b.seq()+1,b.index(),at,at,b.tradeHash(),b.token(),b.side(),b.price(),b.size(),b.pair(),ps);
  }
  static PaperMatchingEngine[] setup(SettlementReplayLabels.Binding b,int context)throws Exception {
    var a=matcher();var c=matcher();long at=b.at();int i=0;
    if(context!=0)for(String token:new TreeSet<>(b.pair())) {
      if(context==3&&i++>0)break;
      long ba=context==2?at-3001:at-1,source=context==1?b.source()-1:ba;
      book(a,token,ba,source);book(c,token,ba,source);
    }
    return new PaperMatchingEngine[]{a,c};
  }
  static void differential(SettlementReplayLabels.Binding b,JsonNode trade,int context)throws Exception {
    var ms=setup(b,context);var a=ms[0];var c=ms[1];
    var left=a.acceptSettlement(b.at(),trade,b);var right=c.accept("TICK",b.at(),trade);
    if(!left.equals(right)||!execution(a).equals(execution(c)))throw new AssertionError("No-order canonical execution state differs");
    BigDecimal quantity=b.portions().stream().map(SettlementReplayLabels.Portion::quantity).reduce(BigDecimal.ZERO,BigDecimal::add);
    var d=a.settlementDiagnostics();
    if(((BigDecimal)d.get("venueQuantity")).compareTo(quantity)!=0||((BigDecimal)d.get("unusedQuantity")).compareTo(quantity)!=0
        ||((BigDecimal)d.get("allocatedQuantity")).signum()!=0||((BigDecimal)d.get("queueAbsorbed")).signum()!=0)throw new AssertionError("Known venue volume not unused/conserved");
    cases++;
    var p=b.portions().get(0);long t=b.at()+10;
    for(var m:ms){for(String token:b.pair())book(m,token,t,t);order(m,p.token(),p.buy(),p.price(),t+1);m.accept("TICK",t+251,node(Map.of()));}
    var next=(com.fasterxml.jackson.databind.node.ObjectNode)trade.deepCopy();next.put("sourceMs",t+252);
    var f=future(b,t+252,true);left=a.acceptSettlement(t+253,next,f);right=c.acceptSettlement(t+253,next,f);
    if(!left.equals(right)||!execution(a).equals(execution(c)))throw new AssertionError("Distinct future component/order continuation differs");
    futureCases++;futureFills+=left.fills().size();
  }
  static boolean duplicateCounterexample(SettlementReplayLabels.Binding b,JsonNode trade)throws Exception {
    var ms=setup(b,0);ms[0].acceptSettlement(b.at(),trade,b);ms[1].accept("TICK",b.at(),trade);
    var p=b.portions().get(0);long t=b.at()+10;
    for(var m:ms){for(String token:b.pair())book(m,token,t,t);order(m,p.token(),p.buy(),p.price(),t+1);m.accept("TICK",t+251,node(Map.of()));}
    var next=(com.fasterxml.jackson.databind.node.ObjectNode)trade.deepCopy();next.put("sourceMs",t+252);var repeated=future(b,t+252,false);
    return !ms[0].acceptSettlement(t+253,next,repeated).equals(ms[1].acceptSettlement(t+253,next,repeated));
  }
  static AccountLedger.State state(AccountLedger.State base,Map<String,AccountLedger.Holding> h,Map<String,AccountLedger.Reservation> o,boolean halted) {
    return new AccountLedger.State(base.version(),base.cash(),base.realized(),base.fees(),base.peakEquity(),base.dayStartEquity(),base.day(),halted,h,o,base.executions());
  }
  static void no(String name,boolean value){if(value)throw new AssertionError("Unsafe proof predicate accepted "+name);rejected.add(name);}
  static void guardTests(Path out)throws Exception {
    Files.createDirectory(out);try(var ledger=CanonicalSessionParityProbe.account(out)) {
      var s=ledger.snapshot();var p=new BigDecimal(".4");
      if(!eligible(matcher(),s,0,false,false))throw new AssertionError("Empty predicate rejected");
      for(String kind:List.of("SUBMITTED_WAITING","ACTIVATION_DUE","ACTIVE","CANCEL_PENDING","CANCEL_DUE","OTHER_TOKEN")) {
        var m=matcher();book(m,"a",1000,1000);order(m,kind.equals("OTHER_TOKEN")?"b":"a",true,p,1001);
        if(Set.of("ACTIVE","CANCEL_PENDING","CANCEL_DUE").contains(kind))m.accept("TICK",1251,node(Map.of()));
        if(kind.startsWith("CANCEL"))m.accept("CANCEL",1252,node(Map.of("id","SYNTHETIC-ORDER")));
        no(kind,eligible(m,s,0,false,false));
      }
      var reserved=new AccountLedger.Reservation("a",true,p,new BigDecimal("5"),new BigDecimal("5"),BigDecimal.ZERO,"RESERVED");
      no("LEDGER_RESERVATION",eligible(matcher(),state(s,Map.of(),Map.of("r",reserved),false),0,false,false));
      no("NONZERO_HOLDING",eligible(matcher(),state(s,Map.of("a",new AccountLedger.Holding(new BigDecimal("5"),new BigDecimal("2"))),Map.of(),false),0,false,false));
      no("PENDING_FOK",eligible(matcher(),s,1,false,false));no("FAILED_SESSION",eligible(matcher(),s,0,true,false));
      no("ENTRY_STOPPED",eligible(matcher(),s,0,false,true));no("HALTED_LEDGER",eligible(matcher(),state(s,Map.of(),Map.of(),true),0,false,false));
    }
  }
  static JsonNode sessionBooks(long source,String bid,String ask) {
    var events=new ArrayList<Object>();for(String token:List.of("a","b"))events.add(Map.of("kind","BOOK","data",Map.of("token",token,"sourceMs",source,
        "bids",List.of(Map.of("price",bid,"size","100")),"asks",List.of(Map.of("price",ask,"size","100")))));
    return node(Map.of("events",events));
  }
  static void sameSession(ResearchSession a,ResearchSession b,AccountLedger la,AccountLedger lb)throws Exception {
    var left=(com.fasterxml.jackson.databind.node.ObjectNode)M.valueToTree(a.report());var right=(com.fasterxml.jackson.databind.node.ObjectNode)M.valueToTree(b.report());
    for(String k:List.of("settlementExperiment","settlementVolumeConservation")){left.remove(k);right.remove(k);}
    if(!left.equals(right)||!la.snapshot().equals(lb.snapshot())||!execution((PaperMatchingEngine)field(a,"matching")).equals(execution((PaperMatchingEngine)field(b,"matching"))))
      throw new AssertionError("Synthetic session/ledger/audit execution continuation differs");
  }
  static Map<String,Object> sessionProof(Path out)throws Exception {
    Files.createDirectory(out);Files.createDirectory(out.resolve("a"));Files.createDirectory(out.resolve("b"));
    var auditA=new ArrayList<Object>();var auditB=new ArrayList<Object>();
    try(var la=CanonicalSessionParityProbe.account(out.resolve("a"));var lb=CanonicalSessionParityProbe.account(out.resolve("b"));
        var a=new ResearchSession(la,ResearchConfig.defaults(),M,out.resolve("a/state.json"),(k,v)->auditA.add(Map.of("kind",k,"data",v)),false,"SYNTHETIC-NOORDER",new ConservedReceiptPool(ConservedReceiptPoolProbe.partial(FrozenStrategySessionProbe.labels()),M),false,OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0);
        var b=new ResearchSession(lb,ResearchConfig.defaults(),M,out.resolve("b/state.json"),(k,v)->auditB.add(Map.of("kind",k,"data",v)),false,"SYNTHETIC-NOORDER",new ConservedReceiptPool(ConservedReceiptPoolProbe.partial(FrozenStrategySessionProbe.labels()),M),false,OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0)) {
      var market=new ResearchMarket(CanonicalSessionParityProbe.CONDITION,"a","b",0,1_000_000,new BigDecimal(".01"),new BigDecimal("5"),new BigDecimal(".07"),1,true,1000,"SYNTHETIC_NOT_MARKET");
      for(var s:List.of(a,b)){s.enableFrozenResearchPolicies();s.acceptReplay("META",1000,node(market),1);s.acceptReplay("FRAME",1251,sessionBooks(1250,".6",".7"),2);s.acceptReplay("TICK",1501,node(Map.of()),3);}
      if(!eligible((PaperMatchingEngine)field(a,"matching"),la.snapshot(),((List<?>)field(a,"pending")).size(),false,false))throw new AssertionError("Synthetic no-order prefix unexpectedly has exposure");
      var trade=(com.fasterxml.jackson.databind.node.ObjectNode)CanonicalSessionParityProbe.trade();trade.put("size","300");
      a.acceptReplay("TRADE",1570,trade,4);b.acceptReplay("TICK",1570,trade,4);sameSession(a,b,la,lb);
      for(var s:List.of(a,b))s.acceptReplay("FRAME",2001,sessionBooks(2000,".4",".6"),5);sameSession(a,b,la,lb);
      for(var s:List.of(a,b))s.acceptReplay("TICK",2251,node(Map.of()),6);sameSession(a,b,la,lb);
      if(eligible((PaperMatchingEngine)field(a,"matching"),la.snapshot(),0,false,false)||!auditA.equals(auditB)
          ||((Number)a.report().get("openOrderCount")).intValue()!=2)throw new AssertionError("Future entry/activation guard or complete audit differs");
      return Map.of("scope","SYNTHETIC_SESSION_LEDGER_AUDIT_CONTINUATION_NOT_MARKET","comparisonPoints",3,"wholeReportExceptTwoExplicitDiagnosticsEqual",true,
          "wholeLedgerAndAuditEqual",true,"futureEntryAndActivationEqual",true,"futureOpenOrders",2,"noOrderPredicateRejectedAfterEntry",true);
    }
  }
  public static void main(String[] args)throws Exception {
    if(args.length!=3)throw new IllegalArgumentException("pool original-identities new-output");Path out=Path.of(args[2]);Files.createDirectory(out);
    var root=M.readTree(Files.readString(Path.of(args[0])));var source=M.readTree(Files.readString(Path.of(args[1])));
    if(source.path("observations").size()!=643)throw new IllegalArgumentException("ALL643 actual source identities required");
    var labels=new ConservedReceiptPool(root,M);SettlementReplayLabels.Binding first=null;JsonNode firstTrade=null;
    for(var row:source.path("observations")) {
      var b=labels.resolve(row.path("seq").asLong(),row.path("eventIndex").asInt(),row.path("at").asLong(),row.path("data"));
      if(first==null){first=b;firstTrade=row.path("data");}
      for(int context=0;context<4;context++)differential(b,row.path("data"),context);
    }
    labels.requireConsumed();guardTests(out.resolve("synthetic-guard-account"));var syntheticSession=sessionProof(out.resolve("synthetic-session-differential"));
    if(!duplicateCounterexample(first,firstTrade)||futureFills==0)throw new AssertionError("Required future-ID counterexample/fill continuation absent");
    var legacy=matcher();var tick=matcher();legacy.accept("TRADE",first.at(),firstTrade);tick.accept("TICK",first.at(),firstTrade);
    if(execution(legacy).equals(execution(tick)))throw new AssertionError("Legacy public print duplicate bookkeeping was ignored");
    var report=new LinkedHashMap<String,Object>();report.put("scope","PROOF_ONLY_SYNTHETIC_BOOK_CONTEXTS_OVER_ACTUAL643_IDENTITIES_NOT_MARKET_REPLAY");
    report.put("poolLogicalSha256",ConservedReceiptPool.hash(Files.readString(Path.of(args[0]))));
    report.put("sourceIdentitiesSha256",ConservedReceiptPool.hash(Files.readString(Path.of(args[1]))));
    report.put("actualIdentities",643);report.put("matcherDifferentialCases",cases);report.put("distinctFutureContinuationCases",futureCases);report.put("syntheticFutureFillEvents",futureFills);
    report.put("guardRejections",rejected);report.put("excludedMatchingFields",new TreeSet<>(EXCLUDED));
    report.put("separateSyntheticSessionDifferential",syntheticSession);
    report.put("allOtherPrivateMatchingFieldsCompared",true);report.put("repeatedComponentFutureDivergenceDetected",true);report.put("legacyPublicPrintBookkeepingDivergenceDetected",true);
    report.put("knownVenueVolumeNotEquivalentToClockOnly",true);report.put("sourceIdentityAndGlobalTransactionUniquenessStillRequired",true);
    for(String k:List.of("fullMatchingStateEquivalent","sessionLevelEquivalenceProven","runtimeOptimizationImplemented","unknownObservationsSkipped","fullAccountReplayAuthorized","marketNetPnlRecomputed","independentPaperQualificationAllowed","liveAllowed"))report.put(k,false);
    Files.writeString(out.resolve("no-order-proof.json"),M.writerWithDefaultPrettyPrinter().writeValueAsString(report)+"\n");
    System.out.println("2572 matcher execution differentials/continuations;12 conservative predicate rejections; duplicate-ID and public-print counterexamples. NO runtime optimization.");
  }
}
