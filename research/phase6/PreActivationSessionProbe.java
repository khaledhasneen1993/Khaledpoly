package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;

/** Actual original97/628 preimages; surrounding pending orders are synthetic, NOT tape replay. */
public final class PreActivationSessionProbe {
  static final com.fasterxml.jackson.databind.ObjectMapper M=NativeReplaySupport.M;
  static void check(boolean value,String why){if(!value)throw new AssertionError(why);}
  static void waiting(IndexedExecutionProbe.Fixture f,JsonNode row,long age)throws Exception {
    long submit=row.path("at").asLong()-age;String token=row.path("data").path("token").asText();
    NoOrderDifferentialProbe.book(f.matcher,token,submit-1,submit-1);
    NoOrderDifferentialProbe.order(f.matcher,token,true,new BigDecimal(".4"),submit);
    f.ledger.reserve("SYNTHETIC-ORDER",token,true,new BigDecimal(".4"),new BigDecimal("5"));
  }
  @SuppressWarnings("unchecked")
  public static void main(String[] args)throws Exception {
    Path pool=Path.of(args[0]),index=Path.of(args[1]),prefix=Path.of(args[2]),out=Path.of(args[3]);Files.createDirectory(out);
    check(CompleteSourceIdentityIndex.sha(Files.readAllBytes(prefix)).equals("2842d45d1fc041fd7c1af8a6ed44403e9c0914e59eaf9c8e4b0515b504c6de8c"),"Prefix changed");
    var rows=M.readTree(Files.readString(prefix)).path("observations");JsonNode first=rows.get(0),second=rows.get(1);
    var checks=new ArrayList<String>();var safe=new ArrayList<Map<String,Object>>();
    for(long age:List.of(20L,54L,249L))try(var f=new IndexedExecutionProbe.Fixture(out.resolve("safe-"+age),pool,index,1792269900000L)){
      f.feed(first);waiting(f,second,age);f.feed(second);f.pristine();var report=f.labels.report();
      check(report.get("temporalWitnessProfile").equals("PRE_ACTIVATION0")&&report.get("unknownPreActivationClockObservations").equals(1L),"Pending route not used");
      check(report.get("knownAppliedObservations").equals(1L)&&report.get("unknownAtomicClockObservations").equals(1L),"Known/unknown routes changed");
      check(report.get("unknownVenueQuantity").equals("UNKNOWN_NOT_ZERO"),"Unknown venue fabricated");
      check(((Map<String,Object>)report.get("sourceIndex")).get("consumedOriginalPreimages").equals(2),"Original identities not consumed");
      check(((BigDecimal)f.matcher.settlementDiagnostics().get("venueQuantity")).compareTo(new BigDecimal("200"))==0,"Known venue changed");
      // The normal session decision may request a later cancellation after the guarded callback.
      check(f.matcher.diagnostics().size()==1&&f.matcher.diagnostics().get(0).get("activationDueMs").equals(second.path("at").asLong()-age+250),"Activation changed");
      IndexedExecutionProbe.rejects(f.labels::requireConsumed);safe.add(report);checks.add("ORIGINAL628_PENDING_AGE_"+age+"_NO_FILL_NO_COMPLETION");
    }
    for(String mode:List.of("DUE","ACTIVE","CANCEL_PENDING","RESERVATION_MISSING","MUTATED_IDENTITY"))try(var f=new IndexedExecutionProbe.Fixture(out.resolve(mode),pool,index,1792269900000L)){
      f.feed(first);waiting(f,second,Set.of("DUE","ACTIVE").contains(mode)?250:20);
      if(mode.equals("ACTIVE"))f.matcher.accept("TICK",second.path("at").asLong(),M.createObjectNode());
      if(mode.equals("CANCEL_PENDING"))f.matcher.accept("CANCEL",second.path("at").asLong()-1,M.valueToTree(Map.of("id","SYNTHETIC-ORDER")));
      if(mode.equals("RESERVATION_MISSING"))f.ledger.cancel("SYNTHETIC-ORDER");
      ObjectNode row=second.deepCopy();if(mode.equals("MUTATED_IDENTITY"))((ObjectNode)row.path("data")).put("size","999");
      IndexedExecutionProbe.rejects(()->f.feed(row));f.pristine();var report=f.labels.report();
      check(report.get("failed").equals(true)&&report.get("unknownPreActivationClockObservations").equals(0L),"Unsafe route not poisoned");
      check(f.ledger.snapshot().halted()&&f.matcher.researchHasNoOrders(),"Unsafe session did not halt/cancel");
      IndexedExecutionProbe.rejects(()->f.session.acceptReplay("TICK",second.path("at").asLong()+1,M.createObjectNode(),629));checks.add(mode+"_HALTS_CANCELS_BLOCKS_CONTINUATION");
    }
    var result=new LinkedHashMap<String,Object>();result.put("scope","TWO_ORIGINAL_PREIMAGES_SYNTHETIC_PENDING_SESSION_NOT_TAPE_REPLAY");result.put("checks",checks);result.put("safeReports",safe);result.put("allFixtureAccountsUnchanged",true);
    for(String flag:List.of("originalTapeReplayed","marketNetPnlRecomputed","independentPaperQualificationAllowed","liveAllowed"))result.put(flag,false);
    M.writerWithDefaultPrettyPrinter().writeValue(out.resolve("preactivation-session-proof.json").toFile(),result);System.out.println(M.writeValueAsString(result));
  }
}
