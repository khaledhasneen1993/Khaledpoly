package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** SYNTHETIC sessions; exact original97/628 and stopped frontier preimages, NOT tape replay. */
public final class SourceLagGuardProbe {
  static final ObjectMapper M=NativeReplaySupport.M;
  static final List<String> rejected=new ArrayList<>(),integration=new ArrayList<>();
  static void check(boolean yes,String why){if(!yes)throw new AssertionError(why);}
  static void reject(Runnable action){try{action.run();}catch(IllegalStateException expected){return;}throw new AssertionError("Unsafe source-lag callback accepted");}
  static JsonNode node(Object x){return M.valueToTree(x);}
  static void order(PaperMatchingEngine m,AccountLedger l,String id,String token,BigDecimal price,long at){
    m.accept("ORDER",at,node(Map.of("id",id,"token",token,"side","BUY","price",price,"size","5")));l.reserve(id,token,true,price,new BigDecimal("5"));
  }
  static void active(AtomicNoOrderGuardProbe.Fixture f){
    PreActivationProof.book(f.matcher,"a",new BigDecimal(".4"),1000);order(f.matcher,f.ledger,"SYNTHETIC-A","a",new BigDecimal(".4"),1001);f.matcher.accept("TICK",1251,node(Map.of()));
  }
  interface Change{void apply(AtomicNoOrderGuardProbe.Fixture f)throws Exception;}
  static void deny(Path root,String name,long at,long source,Change change)throws Exception {
    try(var f=new AtomicNoOrderGuardProbe.Fixture(root.resolve(name))){active(f);change.apply(f);var state=f.ledger.snapshot();var matcher=NoOrderDifferentialProbe.freeze(f.matcher);
      reject(()->f.session.withResearchSourceLagUnfillableWitness(at,source,w->{throw new AssertionError("Unsafe callback entered");}));
      check(state.equals(f.ledger.snapshot())&&matcher.equals(NoOrderDifferentialProbe.freeze(f.matcher)),"Refusal changed execution "+name);rejected.add(name);}
  }
  static void reservationMismatch(AtomicNoOrderGuardProbe.Fixture f,boolean price)throws Exception {
    var s=f.ledger.snapshot();var orders=new HashMap<>(s.orders());
    orders.put("SYNTHETIC-A",new AccountLedger.Reservation("a",true,new BigDecimal(price?".3":".4"),new BigDecimal(price?"5":"6"),new BigDecimal(price?"5":"6"),BigDecimal.ZERO,"OPEN"));
    AtomicNoOrderGuardProbe.set(f.ledger,"state",new AccountLedger.State(s.version(),s.cash(),s.realized(),s.fees(),s.peakEquity(),s.dayStartEquity(),s.day(),s.halted(),s.holdings(),orders,s.executions()));
  }
  @SuppressWarnings("unchecked")
  static void guards(Path root)throws Exception {
    Files.createDirectory(root);
    deny(root,"SOURCE_PLUS_ONE",1300,1252,f->{});deny(root,"SOURCE_FUTURE",1300,1301,f->{});deny(root,"SOURCE_NEGATIVE",1300,-1,f->{});
    deny(root,"MATCHER_CLOCK_REGRESSION",1250,1250,f->{});deny(root,"SESSION_CLOCK_REGRESSION",1300,1251,f->AtomicNoOrderGuardProbe.set(f.session,"now",1400L));
    deny(root,"CANCEL_PENDING",1300,1251,f->f.matcher.accept("CANCEL",1252,node(Map.of("id","SYNTHETIC-A"))));
    deny(root,"CANCEL_DUE",1502,1251,f->f.matcher.accept("CANCEL",1252,node(Map.of("id","SYNTHETIC-A"))));
    deny(root,"SELL_PENDING",1300,1251,f->f.matcher.accept("ORDER",1252,node(Map.of("id","SYNTHETIC-SELL","token","a","side","SELL","price",".9","size","5"))));
    deny(root,"OLDER_ORDER_ELIGIBLE",1510,1260,f->{order(f.matcher,f.ledger,"SYNTHETIC-NEW","a",new BigDecimal(".4"),1252);f.matcher.accept("TICK",1502,node(Map.of()));});
    deny(root,"MISSING_RESERVATION",1300,1251,f->f.ledger.cancel("SYNTHETIC-A"));
    deny(root,"ORPHAN_RESERVATION",1300,1251,f->f.ledger.reserve("orphan","a",true,new BigDecimal(".4"),BigDecimal.ONE));
    deny(root,"RESERVATION_PRICE",1300,1251,f->reservationMismatch(f,true));deny(root,"RESERVATION_SIZE",1300,1251,f->reservationMismatch(f,false));
    deny(root,"HOLDING",1300,1251,f->f.ledger.fill("SYNTHETIC-fill","SYNTHETIC-A",BigDecimal.ONE,new BigDecimal(".4"),BigDecimal.ZERO));
    deny(root,"NONZERO_BASIS",1300,1251,f->AtomicNoOrderGuardProbe.set(f.ledger,"state",AtomicNoOrderGuardProbe.holdings(f.ledger.snapshot(),BigDecimal.ZERO,BigDecimal.ONE)));
    deny(root,"PENDING_FOK",1300,1251,f->((List<Object>)AtomicNoOrderGuardProbe.field(f.session,"pending")).add(null));
    deny(root,"UNHEDGED",1300,1251,f->((Map<String,Long>)AtomicNoOrderGuardProbe.field(f.session,"unhedged")).put("a",1L));
    deny(root,"SESSION_FAILED",1300,1251,f->AtomicNoOrderGuardProbe.set(f.session,"failed",true));deny(root,"ENTRY_STOPPED",1300,1251,f->AtomicNoOrderGuardProbe.set(f.session,"entryStopped",true));
    deny(root,"HALTED",1300,1251,f->f.ledger.halt());deny(root,"LEDGER_FAILED",1300,1251,f->AtomicNoOrderGuardProbe.set(f.ledger,"failed",true));
    deny(root,"CHECKPOINT_CLOSED",1300,1251,f->f.checkpoint.close());deny(root,"LEDGER_CLOSED",1300,1251,f->f.ledger.close());
    deny(root,"EXTERNAL_MODE",1300,1251,f->AtomicNoOrderGuardProbe.set(f.session,"externalMode",true));deny(root,"RECOVERED_CHECKPOINT",1300,1251,f->AtomicNoOrderGuardProbe.set(f.session,"researchRecoveredCheckpoint",true));
    deny(root,"CHECKPOINT_WRITE_FAILED",1300,1251,f->{Path p=f.root.resolve("state.json.tmp");Files.createDirectory(p);reject(()->f.checkpoint.save(Map.of("SYNTHETIC",true)));Files.delete(p);});
    deny(root,"LEDGER_WRITE_FAILED",1300,1251,f->{Path p=f.root.resolve("ledger.json.tmp");Files.createDirectory(p);reject(()->f.ledger.reserve("write-fail","a",true,new BigDecimal(".4"),BigDecimal.ONE));Files.delete(p);});
    deny(root,"NEGATIVE_AVAILABLE_CASH",1300,1251,f->{var s=f.ledger.snapshot();AtomicNoOrderGuardProbe.set(f.ledger,"state",new AccountLedger.State(s.version(),BigDecimal.ZERO,s.realized(),s.fees(),s.peakEquity(),s.dayStartEquity(),s.day(),s.halted(),s.holdings(),s.orders(),s.executions()));});
    try(var f=new AtomicNoOrderGuardProbe.Fixture(root.resolve("RESTORED_LEDGER"))){active(f);f.ledger.close();try(var restored=CanonicalSessionParityProbe.account(f.root)){
      AtomicNoOrderGuardProbe.set(f.session,"ledger",restored);var state=restored.snapshot();
      reject(()->f.session.withResearchSourceLagUnfillableWitness(1300,1251,w->{throw new AssertionError("Restored ledger accepted");}));
      check(state.equals(restored.snapshot()),"Restored rejection changed account");rejected.add("RESTORED_LEDGER");}}
    // Same four-monitor exclusion and witness lifetime as the old empty-order witness, now with ACTIVE orders.
    try(var f=new AtomicNoOrderGuardProbe.Fixture(root.resolve("SAFE_ATOMIC"))){active(f);var escaped=new ResearchSession.NoOrderWitness[1];var workers=new ArrayList<Thread>();var started=new CountDownLatch(4);var finished=new CountDownLatch(4);
      var before=NoOrderDifferentialProbe.freeze(f.matcher);var account=f.ledger.snapshot();
      f.session.withResearchSourceLagUnfillableWitness(1300,1251,w->{w.requireValid();escaped[0]=w;
        for(Object monitor:List.of(f.session,f.ledger,f.matcher,f.checkpoint)){var t=new Thread(()->{started.countDown();synchronized(monitor){finished.countDown();}});workers.add(t);t.start();}
        try{check(started.await(5,TimeUnit.SECONDS),"Workers not started");long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
          while(workers.stream().anyMatch(t->t.getState()!=Thread.State.BLOCKED)&&System.nanoTime()<deadline)Thread.yield();
          check(workers.stream().allMatch(t->t.getState()==Thread.State.BLOCKED)&&finished.getCount()==4,"Guard released monitor inside callback");
          var cross=new java.util.concurrent.atomic.AtomicBoolean();var other=new Thread(()->{try{w.requireValid();}catch(IllegalStateException expected){cross.set(true);}});other.start();other.join(5000);check(!other.isAlive()&&cross.get(),"Cross-thread witness accepted");
        }catch(InterruptedException e){throw new AssertionError(e);}return null;});
      reject(escaped[0]::requireValid);check(finished.await(5,TimeUnit.SECONDS),"Workers not released");for(var t:workers)t.join(5000);
      check(before.equals(NoOrderDifferentialProbe.freeze(f.matcher))&&account.equals(f.ledger.snapshot()),"Guard itself mutated engine/account");
      reject(()->f.session.withResearchSourceLagUnfillableWitness(1300,1251,w->{escaped[0]=w;throw new IllegalStateException("SYNTHETIC callback failure");}));reject(escaped[0]::requireValid);
      reject(()->f.session.withResearchUnfillableWitness(1300,1251,w->{throw new AssertionError("Old preactivation guard weakened");}));
    }
  }
  @SuppressWarnings("unchecked")
  static List<Map<String,Object>> integration(Path pool,Path index,Path prefix,Path root)throws Exception {
    Files.createDirectory(root);var rows=M.readTree(Files.readString(prefix)).path("observations");var first=rows.get(0);var second=rows.get(1);var reports=new ArrayList<Map<String,Object>>();
    check(CompleteSourceIdentityIndex.sha(Files.readAllBytes(prefix)).equals("2842d45d1fc041fd7c1af8a6ed44403e9c0914e59eaf9c8e4b0515b504c6de8c"),"Changed original prefix");
    for(String mode:List.of("SOURCE_EQUAL","SOURCE_BEFORE","SOURCE_PLUS_ONE","OLDER_ORDER_ELIGIBLE","CANCEL_PENDING","RESERVATION_MISSING","MUTATED_IDENTITY"))try(var f=new IndexedExecutionProbe.Fixture(root.resolve(mode),pool,index,1792269900000L)){
      f.feed(first);String token=second.path("data").path("token").asText();long source=second.path("data").path("sourceMs").asLong(),activated=source+(mode.equals("SOURCE_BEFORE")?1:mode.equals("SOURCE_PLUS_ONE")?-1:0);
      PreActivationProof.book(f.matcher,token,new BigDecimal(".4"),activated-251);order(f.matcher,f.ledger,"SYNTHETIC-A",token,new BigDecimal(".4"),activated-250);f.matcher.accept("TICK",activated,node(Map.of()));
      if(mode.equals("OLDER_ORDER_ELIGIBLE")){// A second older order must be checked, not just the newest.
        // Move one already-active actual cutoff earlier; reservations remain exact and unchanged.
        var orders=(Map<?,?>)AtomicNoOrderGuardProbe.field(f.matcher,"orders");AtomicNoOrderGuardProbe.set(orders.get("SYNTHETIC-A"),"activated",source-1);
        order(f.matcher,f.ledger,"SYNTHETIC-NEW",token,new BigDecimal(".4"),activated);}
      if(mode.equals("CANCEL_PENDING"))f.matcher.accept("CANCEL",activated,node(Map.of("id","SYNTHETIC-A")));
      if(mode.equals("RESERVATION_MISSING"))f.ledger.cancel("SYNTHETIC-A");
      ObjectNode row=second.deepCopy();if(mode.equals("MUTATED_IDENTITY"))((ObjectNode)row.path("data")).put("size","999");
      boolean safe=mode.equals("SOURCE_EQUAL")||mode.equals("SOURCE_BEFORE");
      if(safe){f.feed(row);var r=f.labels.report();check(r.get("temporalWitnessProfile").equals("SOURCE_LAG0")&&r.get("unknownSourceLagClockObservations").equals(1L)&&r.get("unknownSourceLagActiveClockObservations").equals(1L),"Wrong new route");
        check(r.get("unknownVenueQuantity").equals("UNKNOWN_NOT_ZERO")&&r.get("knownAppliedObservations").equals(1L)&&((Map<String,Object>)r.get("sourceIndex")).get("consumedOriginalPreimages").equals(2),"Identity/volume scope changed");
        IndexedExecutionProbe.rejects(f.labels::requireConsumed);reports.add(r);
      }else{IndexedExecutionProbe.rejects(()->f.feed(row));check(f.labels.report().get("failed").equals(true)&&f.ledger.snapshot().halted()&&f.matcher.researchHasNoOrders(),"Unsafe session not halted/canceled");IndexedExecutionProbe.rejects(()->f.session.acceptReplay("TICK",row.path("at").asLong()+1,node(Map.of()),629));}
      f.pristine();integration.add(mode+(safe?"_NO_FILL_NO_COMPLETION":"_HALTS_CANCELS_BLOCKS_CONTINUATION"));
    }
    return reports;
  }
  static List<Map<String,Object>> frontiers(Path index,Path input,Path root)throws Exception {
    Files.createDirectory(root);var value=M.readTree(Files.readString(input));check(value.path("scope").asText().equals("EXACT_ORIGINAL_FRONTIER_PREIMAGES_SYNTHETIC_SESSION_NOT_TAPE"),"Wrong frontier scope");var reports=new ArrayList<Map<String,Object>>();
    for(var row:value.path("observations")){
      var identities=new CompleteSourceIdentityIndex(index,CompleteSourceIdentityIndex.Mode.RETAINED_PREIMAGE_SUBSET_ONLY);
      var identity=identities.consume(row.path("seq").asLong(),row.path("eventIndex").asInt(),row.path("at").asLong(),row.path("data"));long at=row.path("at").asLong();
      try(var f=new AtomicNoOrderGuardProbe.Fixture(root.resolve(row.path("profile").asText()))){
        var ds=row.path("originalOrderDiagnostics");long submit=ds.get(0).path("submittedMs").asLong(),activated=ds.get(0).path("activatedMs").asLong();
        for(var d:ds){String token=d.path("token").asText();BigDecimal price=d.path("price").decimalValue(),queue=d.path("initialQueueAhead").decimalValue();
          BigDecimal bookPrice=queue.signum()==0?new BigDecimal(".01"):price,bookSize=queue.signum()==0?new BigDecimal("100"):queue.divide(new BigDecimal("2"));
          f.matcher.accept("BOOK",submit-1,node(Map.of("token",token,"sourceMs",submit-1,"bids",List.of(Map.of("price",bookPrice,"size",bookSize)),"asks",List.of(Map.of("price",price.add(BigDecimal.ONE).divide(new BigDecimal("2")),"size","100")))));
        }
        for(var d:ds)order(f.matcher,f.ledger,d.path("id").asText(),d.path("token").asText(),d.path("price").decimalValue(),submit);
        f.matcher.accept("TICK",activated,node(Map.of()));var before=f.ledger.snapshot();
        var update=f.session.withResearchSourceLagUnfillableWitness(at,identity.source(),w->{w.requireValid();return f.matcher.accept("TICK",at,row.path("data"));});
        check(update.fills().isEmpty()&&update.terminal().isEmpty()&&before.equals(f.ledger.snapshot()),"Frontier envelope changed account/order");
        for(int i=0;i<2;i++)check(((BigDecimal)f.matcher.diagnostics().get(i).get("remainingQueueAhead")).compareTo(ds.get(i).path("initialQueueAhead").decimalValue())==0,"Retained frontier queue altered");
        IndexedExecutionProbe.rejects(identities::requireComplete);reports.add(Map.of("profile",row.path("profile").asText(),"sequence",identity.seq(),"sourceIdentityReport",identities.report(),"syntheticOrderDiagnostics",f.matcher.diagnostics(),"accountUnchanged",true,"originalTapeReplayed",false));
      }
    }
    check(reports.size()==2,"Need both original frontier preimages");return reports;
  }
  static int nativePredicateCases(Path poolPath,Path sourcePath)throws Exception {
    var pool=new ConservedReceiptPool(M.readTree(Files.readString(poolPath)),M);int count=0;
    for(var row:M.readTree(Files.readString(sourcePath)).path("observations")){
      var b=pool.resolve(row.path("seq").asLong(),row.path("eventIndex").asInt(),row.path("at").asLong(),row.path("data"));
      for(int delta:List.of(-1,0,1)){
        var matcher=PreActivationProof.setup(b)[0];matcher.accept("TICK",b.at()+250,node(Map.of()));long source=b.at()+250+delta,arrival=b.at()+320;
        var before=NoOrderDifferentialProbe.freeze(matcher);boolean expected=SourceLagDifferentialProof.proofPredicate(matcher,arrival,source);
        if(expected)check(matcher.researchSourceLagBuys(arrival,source).size()==1,"Generated predicate differs from frozen math");
        else reject(()->matcher.researchSourceLagBuys(arrival,source));
        check(before.equals(NoOrderDifferentialProbe.freeze(matcher)),"Generated predicate mutated execution");count++;
      }
    }
    pool.requireConsumed();check(count==1929,"Incomplete native predicate correspondence");return count;
  }
  public static void main(String[] args)throws Exception {
    Path input=Path.of(args[0]),out=Path.of(args[1]);Files.createDirectory(out);guards(out.resolve("guards"));
    var session=integration(input.resolve("pool/pool.json"),input.resolve("source/complete-index.jsonl"),input.resolve("original-prefix.json"),out.resolve("integration"));
    var frontiers=frontiers(input.resolve("source/complete-index.jsonl"),input.resolve("frontier-preimages.json"),out.resolve("frontiers"));
    int nativeCases=nativePredicateCases(input.resolve("pool/pool.json"),input.resolve("pool/source-identities.json"));
    var result=new LinkedHashMap<String,Object>();result.put("scope","GENERATED_SOURCE_LAG0_ATOMIC_AND_ORIGINAL_PREIMAGE_SYNTHETIC_SESSION_PROOF_NOT_TAPE");result.put("nativePredicateCorrespondenceCases",nativeCases);result.put("rejectionGuards",rejected);result.put("integrationChecks",integration);result.put("safeIndexedSessionReports",session);result.put("frontierEnvelopes",frontiers);
    for(String flag:List.of("fourMonitorsHeldThroughCallback","fourConcurrentUsersBlockedThenReleased","escapedCrossThreadAndExceptionWitnessRejected","guardAloneDoesNotAdvanceOrMutateAccount","oldWitnessMethodsUnchanged","atomicSessionWitnessImplementedInGeneratedBuild","unknownVenueQuantityRemainsUnknown"))result.put(flag,true);
    for(String flag:List.of("originalCoreModified","originalTapeReplayed","completeAccountComparisonPerformed","marketNetPnlRecomputed","independentPaperQualificationAllowed","liveAllowed"))result.put(flag,false);
    M.writerWithDefaultPrettyPrinter().writeValue(out.resolve("source-lag-guard-proof.json").toFile(),result);System.out.println(M.writeValueAsString(result));
  }
}
