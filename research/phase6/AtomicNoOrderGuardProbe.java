package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import com.polybot.hft.state.AtomicJsonState;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** SYNTHETIC safety fixtures only. No market replay, shortcut or financial result. */
public final class AtomicNoOrderGuardProbe {
  static final ObjectMapper M=CanonicalSessionParityProbe.M;
  static final List<String> rejected=new ArrayList<>();
  static Object field(Object o,String key)throws Exception{var f=o.getClass().getDeclaredField(key);f.setAccessible(true);return f.get(o);}
  static void set(Object o,String key,Object value)throws Exception{var f=o.getClass().getDeclaredField(key);f.setAccessible(true);f.set(o,value);}
  static void check(boolean yes,String why){if(!yes)throw new AssertionError(why);}
  static void rejects(Runnable action){try{action.run();}catch(IllegalStateException expected){return;}throw new AssertionError("Unsafe witness accepted");}
  static class Fixture implements AutoCloseable {
    final Path root;final AccountLedger ledger;final ResearchSession session;final PaperMatchingEngine matcher;final AtomicJsonState checkpoint;
    Fixture(Path root)throws Exception{this.root=root;Files.createDirectory(root);ledger=CanonicalSessionParityProbe.account(root);
      session=new ResearchSession(ledger,ResearchConfig.defaults(),M,root.resolve("state.json"),(k,v)->{},false,"SYNTHETIC-GUARD");
      matcher=(PaperMatchingEngine)field(session,"matching");checkpoint=(AtomicJsonState)field(session,"checkpoint");}
    public void close(){try{session.close();}catch(RuntimeException expected){}try{checkpoint.close();}catch(RuntimeException expected){}try{ledger.close();}catch(RuntimeException expected){}}
  }
  interface Change{void apply(Fixture f)throws Exception;}
  static void deny(Path root,String name,Change change)throws Exception {
    try(var f=new Fixture(root.resolve(name))){change.apply(f);var before=NoOrderDifferentialProbe.freeze(f.matcher);var account=f.ledger.snapshot();
      rejects(()->f.session.withResearchNoOrderWitness(w->{throw new AssertionError("Unsafe callback entered");}));
      check(before.equals(NoOrderDifferentialProbe.freeze(f.matcher))&&account.equals(f.ledger.snapshot()),"Guard changed matcher/account "+name);rejected.add(name);}
  }
  static void reservation(Fixture f){f.ledger.reserve("SYNTHETIC-r","a",true,new BigDecimal(".4"),new BigDecimal("5"));}
  static AccountLedger.State holdings(AccountLedger.State s,BigDecimal shares,BigDecimal basis){return new AccountLedger.State(s.version(),s.cash(),s.realized(),s.fees(),s.peakEquity(),s.dayStartEquity(),s.day(),s.halted(),Map.of("a",new AccountLedger.Holding(shares,basis)),s.orders(),s.executions());}
  @SuppressWarnings("unchecked")
  public static void main(String[] args)throws Exception {
    Path out=Path.of(args[0]);Files.createDirectory(out);
    for(String kind:List.of("SUBMITTED","ACTIVATION_DUE","ACTIVE","CANCEL_PENDING","CANCEL_DUE","OTHER_TOKEN"))deny(out,kind,f->{
      NoOrderDifferentialProbe.book(f.matcher,"a",1000,1000);NoOrderDifferentialProbe.order(f.matcher,kind.equals("OTHER_TOKEN")?"b":"a",true,new BigDecimal(".4"),1001);
      if(Set.of("ACTIVE","CANCEL_PENDING","CANCEL_DUE").contains(kind))f.matcher.accept("TICK",1251,M.createObjectNode());
      if(kind.startsWith("CANCEL"))f.matcher.accept("CANCEL",1252,M.valueToTree(Map.of("id","SYNTHETIC-ORDER")));
      if(kind.equals("ACTIVATION_DUE"))set(f.session,"now",1251L);
      if(kind.equals("CANCEL_DUE"))set(f.session,"now",1502L);
      // Due but deliberately NOT ticked. Guard must not advance activation/cancel.
    });
    deny(out,"LEDGER_RESERVATION",AtomicNoOrderGuardProbe::reservation);
    deny(out,"HOLDING",f->{reservation(f);f.ledger.fill("SYNTHETIC-fill","SYNTHETIC-r",new BigDecimal("5"),new BigDecimal(".4"),BigDecimal.ZERO);});
    deny(out,"NONZERO_BASIS",f->set(f.ledger,"state",holdings(f.ledger.snapshot(),BigDecimal.ZERO,BigDecimal.ONE)));
    deny(out,"PENDING_FOK",f->((List<Object>)field(f.session,"pending")).add(null));
    deny(out,"UNHEDGED_TIMER",f->((Map<String,Long>)field(f.session,"unhedged")).put("SYNTHETIC",1L));
    deny(out,"SESSION_FAILED",f->set(f.session,"failed",true));deny(out,"ENTRY_STOPPED",f->set(f.session,"entryStopped",true));
    deny(out,"EXTERNAL_MODE",f->set(f.session,"externalMode",true));deny(out,"RECOVERED_CHECKPOINT",f->set(f.session,"researchRecoveredCheckpoint",true));
    deny(out,"LEDGER_HALTED",f->f.ledger.halt());deny(out,"LEDGER_FAILED",f->set(f.ledger,"failed",true));
    deny(out,"LEDGER_CLOSED",f->f.ledger.close());deny(out,"CHECKPOINT_CLOSED",f->f.checkpoint.close());
    deny(out,"CHECKPOINT_WRITE_FAILED",f->{Path temp=f.root.resolve("state.json.tmp");Files.createDirectory(temp);
      rejects(()->f.checkpoint.save(Map.of("SYNTHETIC",true)));Files.delete(temp);check(!f.checkpoint.researchHealthy(),"Checkpoint failure lost");});
    deny(out,"LEDGER_WRITE_FAILED",f->{Path temp=f.root.resolve("ledger.json.tmp");Files.createDirectory(temp);
      rejects(()->reservation(f));Files.delete(temp);check(f.ledger.persistenceFailed(),"Ledger failure lost");});
    deny(out,"RESTORED_LEDGER",f->{f.ledger.close();try(var restored=CanonicalSessionParityProbe.account(f.root)){
      check(!restored.researchPersistenceHealthy(),"Restored ledger allowed");set(f.session,"ledger",restored);
      rejects(()->f.session.withResearchNoOrderWitness(w->{throw new AssertionError("Restored accepted");}));} });
    try(var f=new Fixture(out.resolve("ATOMIC"))){
      var escaped=new ResearchSession.NoOrderWitness[1];var workers=new ArrayList<Thread>();var started=new CountDownLatch(4);var finished=new CountDownLatch(4);
      f.session.withResearchNoOrderWitness(w->{
        w.requireValid();escaped[0]=w;
        for(Object monitor:List.of(f.session,f.ledger,f.matcher,f.checkpoint)){
          Thread thread=new Thread(()->{started.countDown();synchronized(monitor){finished.countDown();}});workers.add(thread);thread.start();}
        try{check(started.await(5,TimeUnit.SECONDS),"Workers never started");
          long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
          while(workers.stream().anyMatch(t->t.getState()!=Thread.State.BLOCKED)&&System.nanoTime()<deadline)Thread.yield();
          check(workers.stream().allMatch(t->t.getState()==Thread.State.BLOCKED)&&finished.getCount()==4,"Monitor lock escaped callback");
          var crossRejected=new java.util.concurrent.atomic.AtomicBoolean();
          var other=new Thread(()->{try{w.requireValid();}catch(IllegalStateException expected){crossRejected.set(true);}});
          other.start();other.join(5000);check(!other.isAlive()&&crossRejected.get(),"Cross-thread witness accepted/blocked");
        }catch(InterruptedException e){throw new AssertionError(e);}return null;});
      rejects(escaped[0]::requireValid);check(finished.await(5,TimeUnit.SECONDS),"Workers not released");for(var t:workers)t.join(5000);
      rejects(()->f.session.withResearchNoOrderWitness(w->{escaped[0]=w;throw new IllegalStateException("SYNTHETIC callback failure");}));rejects(escaped[0]::requireValid);
      f.session.withResearchNoOrderWitness(w->{w.requireValid();return null;});
    }
    var proof=new LinkedHashMap<String,Object>();proof.put("scope","SYNTHETIC_ATOMIC_EMPTY_EXPOSURE_GUARD_NOT_EXECUTION");proof.put("rejectionGuards",rejected);
    proof.put("sessionLedgerMatcherCheckpointLocksHeld",true);proof.put("fourConcurrentMonitorUsersBlockedThenReleased",true);
    proof.put("witnessInvalidAfterReturnOrException",true);proof.put("crossThreadWitnessRejected",true);
    proof.put("guardDoesNotAdvanceMatcherOrAccount",true);proof.put("persistentWriteFailuresAndClosedStateRejected",true);
    proof.put("atomicGuardImplementedInIsolatedBuild",true);
    for(String flag:List.of("defaultCoreModified","identityConsumerIntegrated","runtimeExecutionSkipImplemented","originalTapeReplayed","marketNetPnlRecomputed","independentPaperQualificationAllowed","liveAllowed"))proof.put(flag,false);
    M.writerWithDefaultPrettyPrinter().writeValue(out.resolve("atomic-guard-proof.json").toFile(),proof);System.out.println(M.writeValueAsString(proof));
  }
}
