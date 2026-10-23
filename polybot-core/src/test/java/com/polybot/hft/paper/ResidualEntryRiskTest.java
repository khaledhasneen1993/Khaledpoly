package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;
import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class ResidualEntryRiskTest {
  @TempDir Path dir;
  final ObjectMapper mapper=new ObjectMapper().findAndRegisterModules();
  BigDecimal b(String s) { return new BigDecimal(s); }

  @Test void exactCostBudgetBoundaryAndDefaultOffPreserveOldDecision() {
    assertThat(ResidualEntryRisk.allows(false,b("5"),b(".34"),b(".64"),b("2.5"),b(".01"))).isTrue();
    assertThat(ResidualEntryRisk.allows(true,b("5"),b(".34"),b(".64"),b("2.5"),b(".01"))).isFalse();
    assertThat(ResidualEntryRisk.allows(true,b("5"),b(".49"),b(".49"),b("2.46"),b(".01"))).isTrue();
    assertThat(ResidualEntryRisk.allows(true,b("5"),b(".49"),b(".49"),b("2.45"),b(".01"))).isFalse();
    assertThatThrownBy(()->ResidualEntryRisk.allows(true,b("5"),b(".49"),b(".49"),b("-1"),b(".01")))
        .isInstanceOf(IllegalArgumentException.class);
  }

  Map<String,Object> prefix(String name,Boolean enabled,String first,String second) throws Exception {
    long base=1800000000000L;var clock=new ClosedLoopReplay.VirtualClock();clock.at=base;
    Path folder=dir.resolve(name);Files.createDirectories(folder);
    var labels=SettlementReplayLabels.load(Path.of("../research/experiments/exit-window-replay-20261018/replay-labels.json"),mapper);
    var limits=new AccountLedger.Limits(b("25"),b("25"),b("250"),b("25"),b("50"));
    try(var ledger=new AccountLedger(folder.resolve("ledger.json"),mapper,b("500"),limits,clock);
        var session=enabled==null
            ? new ResearchSession(ledger,ResearchConfig.defaults(),mapper,folder.resolve("state.json"),(k,v)->{},false,null,labels)
            : new ResearchSession(ledger,ResearchConfig.defaults(),mapper,folder.resolve("state.json"),(k,v)->{},false,null,labels,enabled)) {
      var market=new ResearchMarket("0x"+"1".repeat(64),"a","b",base,base+900000,b(".01"),b("5"),b(".07"),1,true,base,
          "https://gamma-api.polymarket.com/markets?slug=fixture");
      session.accept("META",base,mapper.valueToTree(market));
      for(var token:List.of("a","b")) {
        var price=b(token.equals("a")?first:second);
        session.accept("BOOK",base,mapper.valueToTree(Map.of("token",token,"sourceMs",base,
            "bids",List.of(Map.of("price",price,"size","1000")),
            "asks",List.of(Map.of("price",price.add(b(".01")),"size","1000")))));
      }
      clock.at=base+250;session.accept("TICK",clock.at,mapper.createObjectNode());
      return session.report();
    }
  }

  @Test void existingConstructorAndExplicitOffSubmitSameOrdersWhileCandidateVetoes() throws Exception {
    var old=prefix("old",null,".34",".64");var off=prefix("off",false,".34",".64");
    assertThat(((Number)old.get("submittedOrders")).intValue()).isEqualTo(2);
    assertThat(off.get("submittedOrders")).isEqualTo(old.get("submittedOrders"));
    var candidate=prefix("candidate",true,".34",".64");
    assertThat(((Number)candidate.get("submittedOrders")).intValue()).isZero();
    assertThat(candidate.get("cash")).isEqualTo(b("500"));
    assertThat(candidate.get("residualEntryRiskGuard")).isEqualTo(true);
    assertThat((List<?>)candidate.get("residualEntryRiskRejectSamples")).isNotEmpty();
  }

  @Test void enabledGuardRetainsAdmissibleBalancedEntries() throws Exception {
    assertThat(((Number)prefix("balanced",true,".49",".49").get("submittedOrders")).intValue()).isEqualTo(2);
  }

  @Test void noServiceOrMalformedCliActivation() throws Exception {
    assertThatThrownBy(()->new ResearchSession(null,null,null,dir.resolve("bad"),(k,v)->{},false,null,null,true))
        .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("offline research");
    assertThatThrownBy(()->ResidualRiskReplayMain.main(new String[]{"t","o","c","l","true"}))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
