package com.polybot.hft.paper;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.math.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Actual source identity/tuple parity plus separately scoped SYNTHETIC session guards. */
public final class ConservedReceiptPoolProbe {
  static final ObjectMapper M=CanonicalSessionParityProbe.M;
  static int guards;
  static void reject(Runnable f){try{f.run();}catch(IllegalArgumentException|IllegalStateException expected){guards++;return;}throw new AssertionError("Invalid pool/observation accepted");}
  static ObjectNode partial(ObjectNode old) {
    var root=old.deepCopy();root.put("experiment","CONSERVED-RECEIPT-POOL0");root.put("scope","PARTIAL_SINGLE_MARKET_RECEIPT_POOL_NOT_EXECUTION_MANIFEST");
    root.put("unknownScopedObservation","FAIL_CLOSED");root.put("decision","NO_GO");root.put("newPublicReads",0);
    for(String k:List.of("allOriginalPairObservationsWithinWindow","nativePoolConsumerImplemented","fullAccountReplayAuthorized"))root.put(k,false);
    for(String k:List.of("metadataUsedOnlyForStaticPairIdentityNotDecisionFreshness","nativeSourceIdentityRecheckRequired"))root.put(k,true);
    for(String k:List.of("sourceCensusArtifactZipSha256","sourceAllTradeIdentitiesSha256"))root.put(k,"0".repeat(64));
    var meta=M.createObjectNode();meta.put("sha256","0".repeat(64));meta.put("negativeRisk",false);meta.put("condition",CanonicalSessionParityProbe.CONDITION);meta.set("pair",M.valueToTree(List.of("a","b")));root.set("metadataIdentityReference",meta);
    for(var n:root.path("bindings"))((ObjectNode)n).put("condition",CanonicalSessionParityProbe.CONDITION);return root;
  }
  static ObjectNode fixture(){return partial(ConservedMixedReplayLabelsProbe.fixture("MINT",true));}
  static void selfTests() {
    for(String field:List.of("liveAllowed","independentPaperQualificationAllowed","fullAccountReplayAuthorized","nativePoolConsumerImplemented","allOriginalPairObservationsWithinWindow","candidateAccountSimulated","netPnlRecomputed")) {
      var bad=fixture();bad.put(field,true);reject(()->new ConservedReceiptPool(bad,M));
    }
    for(String field:List.of("partialLabels","nativeSourceIdentityRecheckRequired","metadataUsedOnlyForStaticPairIdentityNotDecisionFreshness")) {
      var bad=fixture();bad.put(field,false);reject(()->new ConservedReceiptPool(bad,M));
    }
    for(String field:List.of("newPublicReads","modelFillsCreated")) {var bad=fixture();bad.put(field,1);reject(()->new ConservedReceiptPool(bad,M));}
    var foreign=fixture();((ObjectNode)foreign.path("metadataIdentityReference")).put("negativeRisk",true);reject(()->new ConservedReceiptPool(foreign,M));
    for(String field:List.of("makingRaw","takingRaw")) {
      var bad=fixture();((ObjectNode)bad.path("bindings").get(0).path("matches").get(0).path("taker")).put(field,999);reject(()->new ConservedReceiptPool(bad,M));
    }
    var duplicate=fixture();((ArrayNode)duplicate.path("bindings").get(0).path("matches")).add(duplicate.path("bindings").get(0).path("matches").get(0).deepCopy());reject(()->new ConservedReceiptPool(duplicate,M));
    var dupBinding=fixture();((ArrayNode)dupBinding.path("bindings")).add(dupBinding.path("bindings").get(0).deepCopy());dupBinding.put("expectedBindingCount",2);reject(()->new ConservedReceiptPool(dupBinding,M));
    var fractional=fixture();((ObjectNode)fractional.path("bindings").get(0).path("matches").get(0).path("maker")).put("takingRaw",1.5);reject(()->new ConservedReceiptPool(fractional,M));
    var wrongRoute=fixture();((ObjectNode)wrongRoute.path("bindings").get(0).path("matches").get(0)).put("matchType","MERGE");reject(()->new ConservedReceiptPool(wrongRoute,M));
    var wrongPair=fixture();((ObjectNode)wrongPair.path("bindings").get(0)).put("condition","0x"+"b".repeat(64));reject(()->new ConservedReceiptPool(wrongPair,M));
    var badEx=fixture();((ObjectNode)badEx.path("bindings").get(0).path("matches").get(0)).put("exchange","0x"+"0".repeat(40));reject(()->new ConservedReceiptPool(badEx,M));
    var incomplete=new ConservedReceiptPool(fixture(),M);reject(incomplete::requireConsumed);
    for(String field:List.of("token","side","price","size","sourceMs","tradeId")) {
      var t=ConservedMixedReplayLabelsProbe.trade(true);if(field.equals("sourceMs"))t.put(field,1261);else t.put(field,switch(field){case "tradeId"->t.path(field).asText()+" ";case "token"->"other";case "side"->"SELL";default->"0.6";});
      var labels=new ConservedReceiptPool(fixture(),M);reject(()->labels.resolve(1,0,1270,t));reject(()->labels.resolve(1,0,1270,ConservedMixedReplayLabelsProbe.trade(true)));
    }
    var read=new ConservedReceiptPool(fixture(),M);read.resolve(1,0,1270,ConservedMixedReplayLabelsProbe.trade(true));reject(()->read.resolve(1,0,1270,ConservedMixedReplayLabelsProbe.trade(true)));
    var unknown=new ConservedReceiptPool(fixture(),M);reject(()->unknown.resolve(2,0,1270,ConservedMixedReplayLabelsProbe.trade(true)));
    var other=ConservedMixedReplayLabelsProbe.trade(true);other.put("token","unrelated-market");var noFallback=new ConservedReceiptPool(fixture(),M);reject(()->noFallback.resolve(2,0,1270,other));
    for(boolean buy:List.of(true,false)) {
      var root=partial(ConservedMixedReplayLabelsProbe.fixture(buy?"MINT":"MERGE",buy));var n=(ObjectNode)root.path("bindings").get(0);
      var q=BigInteger.TEN.pow(40);var c=q.divide(BigInteger.TWO).add(buy?BigInteger.ONE:BigInteger.ONE.negate());var match=n.path("matches").get(0);
      var m=(ObjectNode)match.path("maker");var t=(ObjectNode)match.path("taker");m.put("makingRaw",buy?c:q);m.put("takingRaw",buy?q:c);t.put("makingRaw",buy?q.subtract(c):q);t.put("takingRaw",buy?q:q.subtract(c));n.put("size",new BigDecimal(q,6).toPlainString());
      var trade=ConservedMixedReplayLabelsProbe.trade(buy);trade.put("size",new BigDecimal(q,6).toPlainString());
      int compared=new ConservedReceiptPool(root,M).resolve(1,0,1270,trade).portions().get(0).price().compareTo(new BigDecimal(".5"));
      if(buy?compared<=0:compared>=0)throw new AssertionError("Conservative 28-digit boundary lost");
    }
  }
  static Map<String,Object> sessionGuard(Path root)throws Exception {
    Files.createDirectory(root);try(var ledger=CanonicalSessionParityProbe.account(root)) {
      var labels=new ConservedReceiptPool(partial(FrozenStrategySessionProbe.labels()),M);
      var session=new ResearchSession(ledger,ResearchConfig.defaults(),M,root.resolve("state.json"),(k,v)->{},false,"SYNTHETIC-PARTIAL-POOL",labels,false,OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0);
      session.enableFrozenResearchPolicies();var market=new ResearchMarket(CanonicalSessionParityProbe.CONDITION,"a","b",0,1_000_000,new BigDecimal(".01"),new BigDecimal("5"),new BigDecimal(".07"),1,true,1000,"SYNTHETIC_NOT_MARKET");
      session.acceptReplay("META",1000,M.valueToTree(market),1);session.acceptReplay("FRAME",1251,FrozenStrategySessionProbe.books(1250,".4",".6"),2);session.acceptReplay("TICK",1501,M.createObjectNode(),3);
      var trade=(ObjectNode)CanonicalSessionParityProbe.trade();trade.put("size","300");session.acceptReplay("TRADE",1570,trade,4);labels.requireConsumed();
      var before=ledger.snapshot();var conservation=M.valueToTree(session.report().get("settlementVolumeConservation"));
      if(before.cash().compareTo(new BigDecimal("498"))!=0||before.holdings().get("a").shares().compareTo(new BigDecimal("5"))!=0
          ||conservation.path("venueQuantity").decimalValue().compareTo(new BigDecimal("300"))!=0
          ||conservation.path("queueAbsorbed").decimalValue().compareTo(new BigDecimal("200"))!=0
          ||conservation.path("allocatedQuantity").decimalValue().compareTo(new BigDecimal("5"))!=0
          ||conservation.path("unusedQuantity").decimalValue().compareTo(new BigDecimal("95"))!=0)throw new AssertionError("Canonical original queue/ledger changed");
      reject(()->session.acceptReplay("TRADE",1571,trade,99));reject(()->session.acceptReplay("TICK",1572,M.createObjectNode(),100));
      if(!ledger.snapshot().halted()||((Number)session.report().get("openOrderCount")).intValue()!=0
          ||!ledger.snapshot().cash().equals(before.cash())||!ledger.snapshot().holdings().equals(before.holdings()))throw new AssertionError("Unknown source did not halt/cancel/preserve inventory");
      return Map.of("inputKind","SYNTHETIC_ONLY_NOT_MARKET","canonicalQueueConserved",true,"syntheticShares","5","syntheticCash","498",
          "unknownCoveredTransactionAtWrongCoordinateHaltsCancels",true,"subsequentInputBlocked",true,"existingCashAndInventoryPreserved",true,"session",session.report());
    }
  }
  public static void main(String[] args)throws Exception {
    if(args.length!=3)throw new IllegalArgumentException("pool.json original-identities.json new-output-directory");
    Path poolPath=Path.of(args[0]),sourcePath=Path.of(args[1]),out=Path.of(args[2]);if(Files.size(poolPath)>16_000_000||Files.size(sourcePath)>16_000_000)throw new IllegalArgumentException("Bounded input required");
    var root=M.readTree(Files.readString(poolPath));var original=M.readTree(Files.readString(sourcePath));
    if(!original.path("scope").asText().equals("EXACT642_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE")||original.path("observations").size()!=642)throw new IllegalArgumentException("Exact original identity input required");
    var adapter=new ConservedReceiptPool(root,M);var digest=MessageDigest.getInstance("SHA-256");int count=0;
    for(var row:original.path("observations")) {
      long seq=row.path("seq").asLong();int index=row.path("eventIndex").asInt();var b=adapter.resolve(seq,index,row.path("at").asLong(),row.path("data"));count++;
      for(var p:b.portions())digest.update((seq+"|"+index+"|"+p.identity()+"|"+p.token()+"|"+(p.buy()?"BUY":"SELL")+"|"+p.price().toPlainString()+"|"+p.quantity().toPlainString()+"\n").getBytes(StandardCharsets.UTF_8));
    }
    adapter.requireConsumed();String actual=HexFormat.of().formatHex(digest.digest());if(!actual.equals(root.path("portionsLogicalSha256").asText()))throw new AssertionError("All642 native conservative component tuples differ");
    selfTests();Files.createDirectory(out);var session=sessionGuard(out.resolve("synthetic-session"));
    var report=new LinkedHashMap<String,Object>();report.put("scope","NATIVE_PARTIAL_POOL_PARITY_AND_SYNTHETIC_SESSION_NOT_MARKET_ACCOUNT");report.put("originalObservations",count);report.put("poolReader",adapter.report());report.put("portionsLogicalSha256",actual);report.put("rejectionGuardsPassed",guards);report.put("roundingBoundaryCases",2);
    report.put("syntheticSession",session);report.put("sourceIdentitiesSha256",ConservedReceiptPool.hash(Files.readString(sourcePath)));report.put("poolLogicalSha256",ConservedReceiptPool.hash(Files.readString(poolPath)));
    for(String k:List.of("fullAccountMarketComparisonPerformed","marketNetPnlRecomputed","independentPaperQualificationAllowed","liveAllowed"))report.put(k,false);report.put("modelMarketFillsCreated",0);
    Files.writeString(out.resolve("native-pool-proof.json"),M.writerWithDefaultPrettyPrinter().writeValueAsString(report)+"\n");
    System.out.println("All642 original identities/1516 component tuples, "+guards+" rejection guards and synthetic fail-closed session passed; no market-account replay");
  }
}
