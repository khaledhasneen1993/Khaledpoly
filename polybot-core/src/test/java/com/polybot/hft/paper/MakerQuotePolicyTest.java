package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.polybot.hft.risk.AccountLedger;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class MakerQuotePolicyTest {
  @TempDir Path dir;
  final ResearchSessionTest h = new ResearchSessionTest();

  ResearchConfig config(Integer ticks) throws Exception {
    ObjectNode node = h.mapper.valueToTree(ResearchConfig.defaults());
    if (ticks == null) node.remove("makerImprovementTicks");
    else node.put("makerImprovementTicks", ticks);
    return h.mapper.treeToValue(node, ResearchConfig.class);
  }

  @Test void oldJsonRetainsLegacyPricingAndExplicitCandidateSurvivesStressAndRoundTrip() throws Exception {
    // Compare both forms through the same JSON transport; BigDecimal record equality includes scale.
    assertThat(config(null)).isEqualTo(config(1));
    assertThat(config(null).makerImprovementTicks()).isEqualTo(ResearchConfig.defaults().makerImprovementTicks());
    var candidate = config(0);
    assertThat(candidate.stress().makerImprovementTicks()).isZero();
    assertThat(h.mapper.readValue(h.mapper.writeValueAsString(candidate), ResearchConfig.class)).isEqualTo(candidate);
    assertThatThrownBy(() -> config(-1)).hasRootCauseInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> config(2)).hasRootCauseInstanceOf(IllegalArgumentException.class);
  }

  @Test void bestBidCandidateDoesNotImproveEitherLegOrReduceRiskRequirements() throws Exception {
    h.dir = dir;
    try (var ledger = new AccountLedger(dir.resolve("ledger.json"), h.mapper, h.b("500"), h.limits, h.clock);
         var session = new ResearchSession(ledger, config(0), h.mapper, dir.resolve("session.json"), (k,d)->{})) {
      h.input(session, "META", 0, h.mapper.valueToTree(h.market()));
      h.books(session, 0, "0.4", "0.6", "0.4", "0.6"); h.tick(session, 250);
      assertThat(ledger.snapshot().orders()).hasSize(2);
      assertThat(ledger.snapshot().orders().values()).allSatisfy(o -> assertThat(o.price()).isEqualByComparingTo("0.4"));
      // Exactly the same 2x displayed queue: a 200-share print only exhausts it.
      h.tick(session, 501); h.trade(session, "a", "SELL", "0.4", "200", 502);
      assertThat(session.report().get("fills")).isEqualTo(0);
      h.trade(session, "a", "SELL", "0.4", "1", 503);
      assertThat(session.report().get("fills")).isEqualTo(1);
    }
  }

  @Test void legacyDefaultsStillImproveByOneTick() throws Exception {
    h.dir = dir;
    try (var ledger = new AccountLedger(dir.resolve("ledger.json"), h.mapper, h.b("500"), h.limits, h.clock);
         var session = new ResearchSession(ledger, config(null), h.mapper, dir.resolve("session.json"), (k,d)->{})) {
      h.input(session, "META", 0, h.mapper.valueToTree(h.market()));
      h.books(session, 0, "0.4", "0.6", "0.4", "0.6"); h.tick(session, 250);
      assertThat(ledger.snapshot().orders()).hasSize(2);
      assertThat(ledger.snapshot().orders().values()).allSatisfy(o -> assertThat(o.price()).isEqualByComparingTo("0.41"));
    }
  }
}
