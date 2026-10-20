package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;

/** TWO actual preimages, SYNTHETIC surrounding session, no full tape result. */
public final class IndexedExecutionProbe {
  static final ObjectMapper M=NativeReplaySupport.M;
  static void check(boolean yes,String why){if(!yes)throw new AssertionError(why);}
  static void rejects(Runnable action){try{action.run();}catch(IllegalArgumentException|IllegalStateException expected){return;}throw new AssertionError("Unsafe input accepted");}
  static class Fixture implements AutoCloseable {
    final com.polybot.hft.risk.AccountLedger ledger;final ResearchSession session;final IndexedExecutionLabels labels;final PaperMatchingEngine matcher;
    Fixture(Path root,Path pool,Path index,long end)throws Exception {
      Files.createDirectory(root);ledger=CanonicalSessionParityProbe.account(root);labels=new IndexedExecutionLabels(pool,index,M);
      session=new ResearchSession(ledger,ResearchConfig.defaults(),M,root.resolve("state.json"),(k,v)->{},false,"SYNTHETIC-INDEXED",labels,false,OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0);
      matcher=(PaperMatchingEngine)NoOrderDifferentialProbe.field(session,"matching");session.enableIndexedResearch(labels);
      var market=new ResearchMarket("0x678cc98fe36da747189b6ed6304dfe4a3d65d1e585a6b3537d9f2b7a4ca6dba7",
          "88599287360325233240690982088109814021050513475420535621672707507474151524334",
          "12589566430666404778428222777978747623958961794906352412512658324998006663268",
          1792269000000L,end,new BigDecimal(".01"),new BigDecimal("5"),new BigDecimal(".07"),1,true,1792269582615L,"SYNTHETIC_ENVELOPE_ORIGINAL_STATIC_PAIR");
      session.acceptReplay("META",1792269582615L,M.valueToTree(market),1);
    }
    void feed(JsonNode row){session.acceptReplay("FRAME",row.path("at").asLong(),M.valueToTree(Map.of("events",List.of(Map.of("kind","TRADE","data",row.path("data"))))),row.path("seq").asLong());}
    void pristine(){check(ledger.snapshot().cash().compareTo(new BigDecimal("500"))==0&&ledger.snapshot().holdings().isEmpty()&&ledger.snapshot().executions().isEmpty(),"Fixture account changed");}
    public void close(){session.close();ledger.close();}
  }
  @SuppressWarnings("unchecked")
  public static void main(String[] args)throws Exception {
    Path pool=Path.of(args[0]),index=Path.of(args[1]),prefix=Path.of(args[2]),out=Path.of(args[3]);Files.createDirectory(out);
    JsonNode source=M.readTree(Files.readString(prefix));check(source.path("scope").asText().equals("EXACT_FIRST_TWO_ORIGINAL_PREIMAGES_SYNTHETIC_SESSION_ENVELOPE_NOT_TAPE"),"Prefix scope");
    var observations=source.path("observations");check(observations.size()==2&&observations.get(0).path("seq").asLong()==97&&observations.get(1).path("seq").asLong()==628,"Original prefix coordinates");
    JsonNode first=observations.get(0),second=observations.get(1);long firstAt=first.path("at").asLong();var tests=new ArrayList<String>();Map<String,Object> ordinary,expired;
    try(var f=new Fixture(out.resolve("normal"),pool,index,1792269900000L)){
      f.feed(first);f.feed(second);ordinary=f.labels.report();f.pristine();
      check(ordinary.get("knownAppliedObservations").equals(1L)&&ordinary.get("unknownAtomicClockObservations").equals(1L),"First two routes differ");
      check(((BigDecimal)f.matcher.settlementDiagnostics().get("venueQuantity")).compareTo(new BigDecimal("200"))==0,"Known original97 volume differs");
      check(ordinary.get("unknownVenueQuantity").equals("UNKNOWN_NOT_ZERO")&&((BigDecimal)ordinary.get("unknownObservedPublicSizeNotVenueQuantity")).compareTo(new BigDecimal("12"))==0,"Unknown venue cannot become public/zero volume");
      check(((Map<String,Object>)ordinary.get("sourceIndex")).get("consumedOriginalPreimages").equals(2),"Incomplete prefix consumption");
      tests.add("ORIGINAL97_KNOWN_AND628_ATOMIC_CLOCK");tests.add("UNKNOWN_VENUE_QUANTITY_NOT_ZERO_OR_PUBLIC");
      rejects(f.labels::requireConsumed);tests.add("PREFIX_CANNOT_CERTIFY_FULL_SOURCE_OR_POOL");
    }
    try(var f=new Fixture(out.resolve("expired"),pool,index,firstAt)){
      f.feed(first);f.feed(second);expired=f.labels.report();f.pristine();
      check(expired.get("knownExpiredObservations").equals(1L)&&expired.get("unknownExpiredAtomicClockObservations").equals(1L),"Expiry routes differ");
      check(((Map<String,Object>)expired.get("realReceiptPool")).get("consumedBindings").equals(1),"Known expired binding silently omitted");
      check(((BigDecimal)f.matcher.settlementDiagnostics().get("venueQuantity")).signum()==0&&((BigDecimal)expired.get("knownExpiredComponentQuantityNotApplied")).compareTo(new BigDecimal("200"))==0,"Expired known volume not separate");tests.add("EXPIRY_AFTER_IDENTITY_AND_REAL_POOL_CONSUMPTION");
    }
    for(String mode:List.of("EXPOSURE","MUTATION_AFTER_EXPIRY","DUPLICATE","MISSING_PREFIX","FRAME_INDEX"))try(var f=new Fixture(out.resolve(mode),pool,index,mode.equals("MUTATION_AFTER_EXPIRY")?firstAt:1792269900000L)){
      if(!Set.of("MISSING_PREFIX","FRAME_INDEX").contains(mode))f.feed(first);
      if(mode.equals("EXPOSURE")){String token=first.path("data").path("token").asText();NoOrderDifferentialProbe.book(f.matcher,token,firstAt+1,firstAt+1);NoOrderDifferentialProbe.order(f.matcher,token,true,new BigDecimal(".4"),firstAt+2);}
      if(mode.equals("DUPLICATE"))f.feed(second);
      JsonNode attempt=second;
      if(mode.equals("MUTATION_AFTER_EXPIRY")){ObjectNode n=second.deepCopy();((ObjectNode)n.path("data")).put("size","999");attempt=n;}
      if(mode.equals("FRAME_INDEX"))rejects(()->f.session.acceptReplay("FRAME",firstAt,M.valueToTree(Map.of("events",List.of(
          Map.of("kind","BOOK","data",Map.of("token",first.path("data").path("token").asText(),"sourceMs",firstAt,"bids",List.of(Map.of("price",".01","size","100")),"asks",List.of(Map.of("price",".99","size","100")))),
          Map.of("kind","TRADE","data",first.path("data"))))),97));
      else {JsonNode row=attempt;rejects(()->f.feed(row));}
      check(f.ledger.snapshot().halted()&&((Number)f.session.report().get("openOrderCount")).intValue()==0,"Unsafe session did not halt/cancel");f.pristine();
      var diagnostic=f.labels.report();var identities=(Map<String,Object>)diagnostic.get("sourceIndex");
      check(diagnostic.get("failed").equals(true),"Wrapper not poisoned");
      if(mode.equals("EXPOSURE"))check(identities.get("consumedOriginalPreimages").equals(2)&&diagnostic.get("unknownAtomicClockObservations").equals(0L),"Exposure unknown was applied/skipped");
      else check(identities.get("failed").equals(true),"Failure was not original identity validation");
      if(mode.equals("FRAME_INDEX"))check(((Map<String,Object>)diagnostic.get("lastAttemptedOriginalObservation")).get("eventIndex").equals(1),"Frame index guard not exercised");
      rejects(()->f.session.acceptReplay("TICK",second.path("at").asLong()+1,M.createObjectNode(),629));tests.add(mode+"_HALTS_CANCELS_BLOCKS_CONTINUATION");
    }
    var result=new LinkedHashMap<String,Object>();result.put("scope","TWO_ORIGINAL_PREIMAGES_IN_SYNTHETIC_SESSION_NOT_ORIGINAL_TAPE_REPLAY");result.put("prefixSha256",CompleteSourceIdentityIndex.sha(Files.readAllBytes(prefix)));
    result.put("checks",tests);result.put("ordinary",ordinary);result.put("expired",expired);result.put("allFixtureAccountsUnchanged",true);
    result.put("identityAndAtomicWitnessIntegrated",true);result.put("unknownVenueQuantity","UNKNOWN_NOT_ZERO");
    for(String flag:List.of("fullOriginalTapeReplayed","completeAccountComparisonPerformed","marketNetPnlRecomputed","independentPaperQualificationAllowed","liveAllowed"))result.put(flag,false);
    M.writerWithDefaultPrettyPrinter().writeValue(out.resolve("indexed-execution-proof.json").toFile(),result);System.out.println(M.writeValueAsString(result));
  }
}
