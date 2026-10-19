package com.polybot.hft.paper;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.math.*;
import java.nio.file.*;
import java.util.*;

/** Integrated entry/exit checks on explicit SYNTHETIC feeds, never strategy performance evidence. */
public final class FrozenStrategySessionProbe {
  static final ObjectMapper M=CanonicalSessionParityProbe.M;
  static JsonNode node(Object o){return M.valueToTree(o);}
  static ObjectNode labels() {
    var root=ConservedMixedReplayLabelsProbe.fixture("DIRECT",false);var b=(ObjectNode)root.path("bindings").get(0);
    b.put("seq",4);b.put("at",1570);b.put("sourceMs",1560);b.put("price",".4");b.put("size","300");
    var match=b.path("matches").get(0);var maker=(ObjectNode)match.path("maker");var taker=(ObjectNode)match.path("taker");
    maker.put("makingRaw",120_000_000);maker.put("takingRaw",300_000_000);taker.put("makingRaw",300_000_000);taker.put("takingRaw",120_000_000);return root;
  }
  static JsonNode books(long source,String firstBid,String secondAsk) {
    var events=new ArrayList<Object>();for(String token:List.of("a","b"))events.add(Map.of("kind","BOOK","data",Map.of("token",token,"sourceMs",source,
        "bids",List.of(Map.of("price",token.equals("a")?firstBid:".4","size","100")),"asks",List.of(Map.of("price",token.equals("a")?".6":secondAsk,"size","100")))));
    return node(Map.of("events",events));
  }
  static Map<String,Object> run(Path root,boolean deteriorate)throws Exception {
    Files.createDirectory(root);try(var ledger=CanonicalSessionParityProbe.account(root)) {
      var labels=OfflineSessionLabels.mixed(new ConservedMixedReplayLabels(labels(),M));
      var events=new ArrayList<Map<String,Object>>();
      var session=new ResearchSession(ledger,ResearchConfig.defaults(),M,root.resolve("state.json"),(k,v)->{if(Set.of("HEDGE_DECISION","QW0_DECISION","TAKER_FILL").contains(k))events.add(Map.of("kind",k,"value",v));},false,"SYNTHETIC-FROZEN-POLICY",labels,false,OfflineSessionLabels.Profile.MIXED_BINDING_BRIDGE0);
      session.enableFrozenResearchPolicies();
      boolean rejected=false;try{session.enableFrozenResearchPolicies();}catch(IllegalArgumentException expected){rejected=true;}
      if(!rejected)throw new AssertionError("Policy profile enabled twice");
      var market=new ResearchMarket(CanonicalSessionParityProbe.CONDITION,"a","b",0,1_000_000,new BigDecimal(".01"),new BigDecimal("5"),new BigDecimal(".07"),1,true,1000,"SYNTHETIC_POLICY_TEST_NOT_MARKET");
      session.acceptReplay("META",1000,node(market),1);session.acceptReplay("FRAME",1251,books(1250,".4",".6"),2);session.acceptReplay("TICK",1501,M.createObjectNode(),3);
      var trade=(ObjectNode)CanonicalSessionParityProbe.trade();trade.put("size","300");session.acceptReplay("TRADE",1570,trade,4);labels.requireConsumed();
      if(ledger.snapshot().holdings().get("a").shares().compareTo(new BigDecimal("5"))!=0
          ||ledger.snapshot().holdings().get("a").basis().compareTo(new BigDecimal("2"))!=0)throw new AssertionError("Frozen QW0 entry did not book at original displayed .4 price");
      long seq=5;for(long at:new long[]{2500,4000,5500})session.acceptReplay("FRAME",at,books(at,".4",".6"),seq++);
      session.acceptReplay("FRAME",6571,books(6571,".44",".9"),seq++);
      if(((Number)session.report().get("pendingTakers")).intValue()!=0)throw new AssertionError("Taker sent before counterpart cancellation ACK");
      session.acceptReplay("TICK",6821,M.createObjectNode(),seq++);
      if(((Number)session.report().get("pendingTakers")).intValue()!=1)throw new AssertionError("Frozen profitable sale not planned after ACK");
      if(deteriorate)session.acceptReplay("FRAME",7071,books(7071,".42",".9"),seq++);
      else session.acceptReplay("TICK",7071,M.createObjectNode(),seq++);
      if(deteriorate) {
        if(ledger.snapshot().cash().compareTo(new BigDecimal("498"))!=0||ledger.snapshot().holdings().get("a").shares().compareTo(new BigDecimal("5"))!=0
            ||ledger.snapshot().fees().signum()!=0||events.stream().anyMatch(e->e.get("kind").equals("TAKER_FILL")))throw new AssertionError("Deteriorated actual net edge must reject FOK, not manufacture an exit");
      } else if(ledger.snapshot().cash().compareTo(new BigDecimal("500.11376"))!=0||ledger.snapshot().realized().compareTo(new BigDecimal(".11376"))!=0
          ||ledger.snapshot().fees().compareTo(new BigDecimal(".08624"))!=0||ledger.snapshot().holdings().get("a").shares().signum()!=0)
        throw new AssertionError("Synthetic fee-positive canonical exit/fee/account differs");
      var result=new LinkedHashMap<String,Object>();result.put("inputKind","SYNTHETIC_NOT_MARKET");result.put("deterioratedBeforeActualFok",deteriorate);
      result.put("events",events);result.put("session",session.report());return result;
    }
  }
  public static void main(String[] args)throws Exception {
    if(args.length!=1)throw new IllegalArgumentException("new-out directory required");Path out=Path.of(args[0]);Files.createDirectory(out);
    var result=new LinkedHashMap<String,Object>();result.put("scope","INTEGRATED_FROZEN_POLICIES_SYNTHETIC_ONLY_NOT_MARKET_PNL");
    result.put("positive",run(out.resolve("positive"),false));result.put("netEdgeRejected",run(out.resolve("net-edge-rejected"),true));
    result.put("defaultCoreFilesModified",0);result.put("modelMarketFillsCreated",0);result.put("marketNetPnlRecomputed",false);
    result.put("fullAccountMarketComparisonPerformed",false);result.put("independentPaperQualificationAllowed",false);result.put("liveAllowed",false);
    Files.writeString(out.resolve("strategy-proof.json"),M.writerWithDefaultPrettyPrinter().writeValueAsString(result)+"\n");
    System.out.println("Synthetic QW0 entry through2x queue, cancellation ACK, profitable sell and deteriorated execution-net rejection passed");
  }
}
