package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class SettlementReplayTest {
  @TempDir Path dir;
  final ObjectMapper mapper=new ObjectMapper().findAndRegisterModules();
  final long base=1800000000000L;
  BigDecimal b(String value) { return new BigDecimal(value); }
  JsonNode book(String token,long at,String bid,String ask,String size) {
    return mapper.valueToTree(Map.of("token",token,"sourceMs",at,"bids",List.of(Map.of("price",bid,"size",size)),
        "asks",List.of(Map.of("price",ask,"size","100"))));
  }
  SettlementReplayLabels.Binding binding(long source,String id,String price,String quantity) {
    return new SettlementReplayLabels.Binding(1,0,source,source,"","b","BUY",b("0.6"),b(quantity),Set.of("a","b"),
        List.of(new SettlementReplayLabels.Portion(id,"a",true,b(price),b(quantity))));
  }
  JsonNode trade(long source) { return mapper.valueToTree(Map.of("sourceMs",source,"tradeId","fixture")); }
  PaperMatchingEngine engine(String depth) {
    var engine=new PaperMatchingEngine(100,100,2000,b("2"));
    engine.accept("BOOK",1000,book("a",1000,"0.4","0.6",depth));
    engine.accept("BOOK",1000,book("b",1000,"0.4","0.6","100"));
    engine.accept("ORDER",1000,mapper.valueToTree(Map.of("id","one","token","a","side","BUY","price","0.4","size","5")));
    engine.accept("TICK",1101,mapper.createObjectNode());return engine;
  }

  @Test void partialComponentQueueAndDedupConserveVenueVolume() {
    var engine=engine("10");
    assertThat(engine.acceptSettlement(1102,trade(1102),binding(1102,"first","0.39","22")).fills())
        .singleElement().satisfies(f->assertThat(f.size()).isEqualByComparingTo("2"));
    assertThat(engine.acceptSettlement(1103,trade(1103),binding(1103,"first","0.39","22")).fills()).isEmpty();
    assertThat(engine.acceptSettlement(1104,trade(1104),binding(1104,"second","0.39","3")).fills())
        .singleElement().satisfies(f->assertThat(f.size()).isEqualByComparingTo("3"));
    var report=engine.settlementDiagnostics();
    assertThat((BigDecimal)report.get("venueQuantity")).isEqualByComparingTo("25");
    assertThat((BigDecimal)report.get("queueAbsorbed")).isEqualByComparingTo("20");
    assertThat((BigDecimal)report.get("allocatedQuantity")).isEqualByComparingTo("5");
  }

  @Test void sellExitConsumesDirectSharesButNotComplementaryMintAggregate() {
    var engine=new PaperMatchingEngine(100,100,2000,b("2"));
    var own=(ObjectNode)book("a",1000,"0.46","0.47","100");
    ((ObjectNode)own.path("asks").get(0)).put("size","5"); // unchanged queue multiplier: ten ahead
    engine.accept("BOOK",1000,own);
    engine.accept("BOOK",1000,book("b",1000,"0.53","0.54","100"));
    engine.accept("ORDER",1000,mapper.valueToTree(Map.of("id","exit","token","a","side","SELL","price","0.47","size","5")));
    engine.accept("TICK",1101,mapper.createObjectNode());
    var direct=new SettlementReplayLabels.Binding(1,0,1102,1102,"","a","BUY",b("0.47"),b("13"),Set.of("a","b"),
        List.of(new SettlementReplayLabels.Portion("direct","a",false,b("0.47"),b("13"))));
    assertThat(engine.acceptSettlement(1102,trade(1102),direct).fills()).singleElement()
        .satisfies(f->{assertThat(f.buy()).isFalse();assertThat(f.size()).isEqualByComparingTo("3");});
    var mint=new SettlementReplayLabels.Binding(2,0,1103,1103,"","a","BUY",b("0.47"),b("5"),Set.of("a","b"),
        List.of(new SettlementReplayLabels.Portion("mint","b",true,b("0.53"),b("5"))));
    assertThat(engine.acceptSettlement(1103,trade(1103),mint).fills()).isEmpty();
    // No fallback aggregate credit, no queue cancellation credit, two SELL shares still outstanding.
    var later=new SettlementReplayLabels.Binding(3,0,1104,1104,"","a","BUY",b("0.47"),b("2"),Set.of("a","b"),
        List.of(new SettlementReplayLabels.Portion("later-direct","a",false,b("0.47"),b("2"))));
    assertThat(engine.acceptSettlement(1104,trade(1104),later).fills()).singleElement()
        .satisfies(f->assertThat(f.size()).isEqualByComparingTo("2"));
  }

  @Test void cancelDueGapAndOlderThanBookCannotFillOrResurrect() {
    var engine=engine("0");
    engine.accept("CANCEL",1102,mapper.valueToTree(Map.of("id","one")));
    assertThat(engine.acceptSettlement(1202,trade(1202),binding(1202,"cancel","0.39","100")).fills()).isEmpty();
    engine=engine("0");engine.accept("GAP",1102,mapper.valueToTree(Map.of("tokens",List.of("a","b"))));
    engine.accept("BOOK",1103,book("a",1103,"0.4","0.6","0"));
    engine.accept("BOOK",1103,book("b",1103,"0.4","0.6","0"));
    assertThat(engine.acceptSettlement(1104,trade(1104),binding(1104,"gap","0.39","100")).fills()).isEmpty();
    engine=engine("0");engine.accept("BOOK",1103,book("a",1103,"0.4","0.6","0"));
    assertThat(engine.acceptSettlement(1104,trade(1102),binding(1102,"old","0.39","100")).fills()).isEmpty();
  }

  @Test void multiOrderSharedVolumeDoesNotGiveEveryOrderFullAggregate() {
    var engine=engine("10");
    engine.accept("ORDER",1101,mapper.valueToTree(Map.of("id","two","token","a","side","BUY","price","0.4","size","5")));
    engine.accept("TICK",1202,mapper.createObjectNode());
    var result=engine.acceptSettlement(1203,trade(1203),binding(1203,"shared","0.39","26"));
    assertThat(result.fills().stream().map(PaperMatchingEngine.Fill::size).reduce(BigDecimal.ZERO,BigDecimal::add))
        .isEqualByComparingTo("6");
  }

  ObjectNode labelsRoot(JsonNode data) throws Exception {
    var root=(ObjectNode)mapper.readTree(Files.readString(Path.of("../research/experiments/settlement-lab0-20261018/replay-labels.json")));
    var row=(ObjectNode)root.path("bindings").get(0).deepCopy();
    row.put("seq",55);row.put("eventIndex",0);row.put("at",base+502);row.put("sourceMs",base+502);
    row.put("token","b");row.put("price","0.6");row.put("size","100");
    row.set("pair",mapper.valueToTree(List.of("a","b")));
    row.put("publicTradeIdSha256",HexFormat.of().formatHex(SettlementReplayLabels.digest(data.path("tradeId").asText().getBytes(java.nio.charset.StandardCharsets.UTF_8))));
    var match=(ObjectNode)row.path("matches").get(0).deepCopy();
    ((ObjectNode)match.path("maker")).put("token","a").put("makingRaw",40000000).put("takingRaw",100000000);
    ((ObjectNode)match.path("taker")).put("token","b").put("makingRaw",60000000).put("takingRaw",100000000);
    row.set("matches",mapper.createArrayNode().add(match));root.set("bindings",mapper.createArrayNode().add(row));return root;
  }

  @Test void loaderRejectsNonconservedComponentsWrongBindingAndWrongTape() throws Exception {
    var data=mapper.valueToTree(Map.of("token","b","side","BUY","price","0.6","size","100","sourceMs",base+502,"tradeId","fixture"));
    var root=labelsRoot(data);var labels=new SettlementReplayLabels(root,mapper,"fixture");
    assertThatThrownBy(()->labels.resolve(55,0,base+503,data)).isInstanceOf(IllegalArgumentException.class);
    ((ObjectNode)root.path("bindings").get(0).path("matches").get(0).path("maker")).put("makingRaw",40000001);
    assertThatThrownBy(()->new SettlementReplayLabels(root,mapper,"fixture")).isInstanceOf(IllegalArgumentException.class);
    Path wrong=dir.resolve("wrong.jsonl");Files.writeString(wrong,"different");
    assertThatThrownBy(()->labels.verifyTape(wrong)).isInstanceOf(IllegalArgumentException.class);
  }

  @Test void settlementFillFlowsThroughRealLedgerAndExistingFeeAwareRiskExit() throws Exception {
    var clock=new ClosedLoopReplay.VirtualClock();clock.at=base;
    var limits=new AccountLedger.Limits(b("25"),b("25"),b("250"),b("25"),b("50"));
    var data=mapper.valueToTree(Map.of("token","b","side","BUY","price","0.6","size","100","sourceMs",base+502,"tradeId","fixture"));
    var labels=new SettlementReplayLabels(labelsRoot(data),mapper,"fixture");
    try (var ledger=new AccountLedger(dir.resolve("ledger.json"),mapper,b("500"),limits,clock);
        var session=new ResearchSession(ledger,ResearchConfig.defaults(),mapper,dir.resolve("session.json"),(k,v)->{},false,null,labels)) {
      var market=new ResearchMarket("0x"+"1".repeat(64),"a","b",base,base+900000,b("0.01"),b("1"),b("0.07"),1,true,base,
          "https://gamma-api.polymarket.com/markets?slug=fixture");
      session.accept("META",base,mapper.valueToTree(market));
      session.accept("BOOK",base,book("a",base,"0.4","0.6","100"));
      session.accept("BOOK",base,book("b",base,"0.4","0.6","100"));
      clock.at=base+250;session.accept("TICK",clock.at,mapper.createObjectNode());
      clock.at=base+501;session.accept("TICK",clock.at,mapper.createObjectNode());
      clock.at=base+502;session.acceptReplay("TRADE",clock.at,data,55);
      assertThat(ledger.snapshot().holdings().get("a").shares()).isEqualByComparingTo("5");
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("497.95");
      for (long offset:new long[]{30502,30752,30753,31003}) {
        clock.at=base+offset;
        if (offset==30502 || offset==30753) {
          session.accept("BOOK",clock.at,book("a",clock.at,offset==30502?"0.30":"0.29","0.50","100"));
          session.accept("BOOK",clock.at,book("b",clock.at,"0.40","0.80","100"));
        } else session.accept("TICK",clock.at,mapper.createObjectNode());
      }
      assertThat(ledger.snapshot().holdings().get("a").shares()).isEqualByComparingTo("0");
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("499.32793");
      assertThat(ledger.snapshot().fees()).isEqualByComparingTo("0.07207");
      assertThat(session.report().get("halted")).isEqualTo(true);
      assertThat(session.report().get("independentPaperQualificationAllowed")).isEqualTo(false);
    }
  }
}
