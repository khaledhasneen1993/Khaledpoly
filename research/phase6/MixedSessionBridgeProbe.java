package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.math.*;
import java.nio.file.*;
import java.util.*;

/** Full canonical PAPER ledger wiring on SYNTHETIC input only. Not a strategy result. */
public final class MixedSessionBridgeProbe {
  static final ObjectMapper M=CanonicalSessionParityProbe.M;
  static JsonNode fixture() {
    var root=ConservedMixedReplayLabelsProbe.fixture("DIRECT",false);
    var b=(ObjectNode)root.path("bindings").get(0);b.put("seq",4);b.put("at",1570);b.put("sourceMs",1560);b.put("price",".4");return root;
  }
  static OfflineSessionLabels labels(){return OfflineSessionLabels.mixed(new ConservedMixedReplayLabels(fixture(),M));}
  static void rejected(Runnable run){try{run.run();}catch(IllegalArgumentException|IllegalStateException expected){return;}throw new AssertionError("Unsafe session bridge accepted");}
  public static void main(String[] args)throws Exception {
    if(args.length!=1)throw new IllegalArgumentException("new-out directory required");Path root=Path.of(args[0]);Files.createDirectory(root);
    Map<String,Object> snapshot;int guards=0;
    Path positive=root.resolve("positive");Files.createDirectory(positive);
    try(var ledger=CanonicalSessionParityProbe.account(positive)) {
      var labels=labels();var session=new ResearchSession(ledger,ResearchConfig.defaults(),M,positive.resolve("state.json"),(k,v)->{},false,"SYNTHETIC-BRIDGE",labels,false,OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0);
      CanonicalSessionParityProbe.feed(session,true);labels.requireConsumed();
      if(ledger.snapshot().cash().compareTo(new BigDecimal("497.95"))!=0||ledger.snapshot().holdings().get("a").shares().compareTo(new BigDecimal("5"))!=0
          || ledger.snapshot().holdings().get("a").basis().compareTo(new BigDecimal("2.05"))!=0)throw new AssertionError("Canonical ledger did not book actual matcher fixture");
      var before=ledger.snapshot();session.acceptReplay("TRADE",1580,CanonicalSessionParityProbe.trade(),5);
      if(!before.equals(ledger.snapshot()))throw new AssertionError("Duplicate public aggregate changed ledger");
      var unknown=(ObjectNode)CanonicalSessionParityProbe.trade();unknown.put("tradeId","{\"transaction_hash\":\"0x"+"2".repeat(64)+"\"}");
      rejected(()->session.acceptReplay("TRADE",1590,unknown,6));guards++;
      if(!ledger.snapshot().halted()||((Number)session.report().get("openOrderCount")).intValue()!=0)throw new AssertionError("Unknown source did not halt/cancel account");
      rejected(()->session.acceptReplay("TICK",1600,M.createObjectNode(),7));guards++;
      if(!ledger.snapshot().cash().equals(before.cash())||!ledger.snapshot().holdings().equals(before.holdings()))throw new AssertionError("Failed-source guard changed booked inventory/cash");
      snapshot=new TreeMap<>(session.report());
    }
    for(String mode:List.of("external","existing-state","nonempty-ledger","profile-mismatch","missing-labels")) {
      Path path=root.resolve(mode);Files.createDirectory(path);
      try(var ledger=CanonicalSessionParityProbe.account(path)) {
        if(mode.equals("existing-state"))Files.writeString(path.resolve("state.json"),"{}");
        if(mode.equals("nonempty-ledger"))ledger.reserve("fixture-reservation","a",true,new BigDecimal(".4"),new BigDecimal("5"));
        rejected(()->new ResearchSession(ledger,ResearchConfig.defaults(),M,path.resolve("state.json"),(k,v)->{},mode.equals("external"),"TEST",
            mode.equals("missing-labels")?null:labels(),false,mode.equals("profile-mismatch")?OfflineSessionLabels.Profile.LEGACY:OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0));guards++;
      }
    }
    var report=new LinkedHashMap<String,Object>();report.put("scope","SYNTHETIC_CANONICAL_SESSION_BRIDGE_NOT_MARKET_OR_PROFIT_PROOF");
    report.put("syntheticEntryBookedThroughCanonicalStrategyMatcherLedger",true);report.put("syntheticCashAfterOneMakerFill","497.95");
    report.put("syntheticShares","5");report.put("syntheticBasis","2.05");report.put("duplicateAggregateChangedLedger",false);
    report.put("rejectionGuardsPassed",guards);report.put("unknownSourceHaltsCancelsAndBlocksSubsequentInput",true);
    report.put("modelMarketFillsCreated",0);report.put("marketNetPnlRecomputed",false);report.put("fullAccountStrategyComparisonPerformed",false);
    report.put("frozenQw0AndFeePositivePoliciesIntegrated",false);report.put("independentPaperQualificationAllowed",false);report.put("liveAllowed",false);
    report.put("syntheticTerminalSessionReport",snapshot);
    Files.writeString(root.resolve("bridge-proof.json"),M.writerWithDefaultPrettyPrinter().writeValueAsString(report)+"\n");
    System.out.println("Canonical synthetic maker entry, ledger booking, duplicate suppression and "+guards+" fail-closed session guards passed");
  }
}
