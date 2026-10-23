package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;
import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class EntryDecisionWitnessTest {
  @TempDir Path dir;
  final ObjectMapper mapper=new ObjectMapper().findAndRegisterModules();
  BigDecimal b(String s) { return new BigDecimal(s); }
  final String condition="0x"+"1".repeat(64);

  Map<String,Object> run(String name,boolean trace,String first,String second) throws Exception {
    long base=1800000000000L;var clock=new ClosedLoopReplay.VirtualClock();clock.at=base;
    Path folder=dir.resolve(name);Files.createDirectories(folder);
    var labels=SettlementReplayLabels.load(Path.of("../research/experiments/exit-window-replay-20261018/replay-labels.json"),mapper);
    var limits=new AccountLedger.Limits(b("25"),b("25"),b("250"),b("25"),b("50"));
    try(var ledger=new AccountLedger(folder.resolve("ledger.json"),mapper,b("500"),limits,clock);
        var session=new ResearchSession(ledger,ResearchConfig.defaults(),mapper,folder.resolve("state.json"),(k,v)->{},false,null,labels,true)) {
      var witness=new EntryDecisionWitness(List.of(new EntryDecisionWitness.Window(condition,base,base+1000)));
      if(trace) session.enableDecisionWitness(witness);
      var m=new ResearchMarket(condition,"a","b",base,base+900000,b(".01"),b("5"),b(".07"),1,true,base,"https://gamma-api.polymarket.com/markets?slug=fixture");
      session.accept("META",base,mapper.valueToTree(m));
      assertThatThrownBy(()->session.enableDecisionWitness(witness)).isInstanceOf(IllegalArgumentException.class);
      for(var token:List.of("a","b")) {
        var p=b(token.equals("a")?first:second);
        session.accept("BOOK",base,mapper.valueToTree(Map.of("token",token,"sourceMs",base,
            "bids",List.of(Map.of("price",p,"size","1000")),
            "asks",List.of(Map.of("price",p.add(b(".01")),"size","1000")))));
      }
      clock.at=base+250;session.accept("TICK",clock.at,mapper.createObjectNode());
      return session.report();
    }
  }

  @Test void boundedObservationDoesNotChangeAnyOtherReportField() throws Exception {
    for(var prices:List.of(List.of(".34",".64"),List.of(".49",".49"))) {
      var off=run("off"+prices.get(0),false,prices.get(0),prices.get(1));
      var on=new LinkedHashMap<>(run("on"+prices.get(0),true,prices.get(0),prices.get(1)));
      var rows=(List<Map<String,Object>>)on.remove("entryDecisionWitnesses");
      assertThat(on).isEqualTo(off);
      assertThat(rows).isNotEmpty();
      assertThat(rows.getFirst().get("firstObservedVolatility")).isNull();
      assertThat(rows.getLast().get("actualDecisionReasonDelta"))
          .isEqualTo(Map.of(prices.get(0).equals(".34")?"ENTRY_RESIDUAL_LOSS_BUDGET":"PAIR_SUBMITTED",1L));
      assertThat(rows.getLast()).containsKeys("market","firstBook","secondBook","requiredEdge","quantity","nextDecisionMs");
    }
  }

  @Test void boundsAndNoServiceActivationFailClosed() {
    assertThatThrownBy(()->new EntryDecisionWitness(List.of())).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(()->new EntryDecisionWitness(List.of(new EntryDecisionWitness.Window(condition,0,3001))))
        .isInstanceOf(IllegalArgumentException.class);
    var w=new EntryDecisionWitness(List.of(new EntryDecisionWitness.Window(condition,10,20)));
    assertThat(w.selects(condition,9)).isFalse();assertThat(w.selects(condition,10)).isTrue();
    assertThat(w.selects(condition,21)).isFalse();
    for(int i=0;i<500;i++) w.append(Map.of("at",i));
    assertThatThrownBy(()->w.append(Map.of())).isInstanceOf(IllegalStateException.class);
    assertThatThrownBy(()->EntryDecisionWitnessReplayMain.main(new String[]{})).isInstanceOf(IllegalArgumentException.class);
  }
}
