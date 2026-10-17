package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class AdaptivePaperPolicyTest {
  @Test
  void latencyIsReproducibleBoundedAndActionSpecific() {
    var p = new LatencyProfile(250, 500, 42);
    var copy = new LatencyProfile(250, 500, 42);
    var delays = new java.util.HashSet<Long>();
    for (int i = 0; i < 100; i++) {
      long delay = p.delay("activate", "order" + i);
      assertThat(delay).isBetween(250L, 750L);
      assertThat(copy.delay("activate", "order" + i)).isEqualTo(delay);
      delays.add(delay);
    }
    assertThat(delays.size()).isGreaterThan(1);
    assertThat(new LatencyProfile(250, 0, 42).delay("cancel", "x")).isEqualTo(250);
    assertThatThrownBy(() -> new LatencyProfile(0, 60001, 0))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void makerWaitShrinksWithExpiryAndVolatility() {
    assertThat(PairPolicy.secondLegWaitMs(900000, 30000, BigDecimal.ZERO)).isEqualTo(5000);
    assertThat(PairPolicy.secondLegWaitMs(4000, 30000, BigDecimal.ZERO)).isEqualTo(1000);
    assertThat(PairPolicy.secondLegWaitMs(900000, 30000, new BigDecimal(".01"))).isEqualTo(2500);
    assertThat(PairPolicy.secondLegWaitMs(0, 30000, BigDecimal.ZERO)).isZero();
    assertThat(ResearchConfig.defaults().stress().latencyJitterMs()).isEqualTo(500);
  }

  @Test
  void fillRateCountsOrdersOnceAcrossPartialFills() {
    var m = new ExperimentMetrics();
    m.intent("one", 1000, "m", new BigDecimal(".03"), "ENTRY");
    m.intent("two", 1000, "m", new BigDecimal(".03"), "ENTRY");
    m.fill(
        new PaperMatchingEngine.Fill("one", "a", true, new BigDecimal(".4"), BigDecimal.ONE, 1100),
        BigDecimal.ZERO,
        "MAKER");
    m.fill(
        new PaperMatchingEngine.Fill("one", "a", true, new BigDecimal(".4"), BigDecimal.ONE, 1200),
        BigDecimal.ZERO,
        "MAKER");
    assertThat(m.report().get("filledOrders")).isEqualTo(1);
    assertThat((BigDecimal) m.report().get("orderFillRate")).isEqualByComparingTo(".5");
    assertThat(m.report().get("decisionToFillP95Ms")).isEqualTo(200L);
  }
}
