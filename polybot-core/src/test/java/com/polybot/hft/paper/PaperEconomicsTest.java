package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import java.math.*;
import java.util.*;
import org.junit.jupiter.api.*;

class PaperEconomicsTest {
  BigDecimal b(String s) {
    return new BigDecimal(s);
  }

  @Test
  void feesUseCurrentCurveAndMakersNeverAssumeRewards() {
    var fees = new FeeModel(b("0.07"), 1);
    assertThat(fees.fee(b("100"), b("0.5"), false)).isEqualByComparingTo("1.75");
    assertThat(fees.fee(b("100"), b("0.5"), true)).isEqualByComparingTo("0");
    assertThat(fees.fee(b("100"), b("0.1"), false)).isEqualByComparingTo("0.63");
  }

  @Test
  void takerSweepsDepthAndRejectsIncompleteFok() {
    var levels = new TreeMap<BigDecimal, BigDecimal>();
    levels.put(b("0.5"), b("3"));
    levels.put(b("0.6"), b("4"));
    var result = DepthExecution.sweep(levels, true, b("5"), b("0.6"), new FeeModel(b("0.07"), 1));
    assertThat(result.notional()).isEqualByComparingTo("2.7");
    assertThat(result.fee()).isEqualByComparingTo("0.08610");
    assertThatThrownBy(
            () -> DepthExecution.sweep(levels, true, b("5"), b("0.5"), new FeeModel(b("0.07"), 1)))
        .isInstanceOf(IllegalStateException.class);
  }

  @Test
  void dynamicEdgePenalizesExpiryLatencyThinDepthAndInventory() {
    var base = PairPolicy.requiredEdge(b("0.01"), b("0"), 600, b("1000"), 100, b("0"));
    var risky = PairPolicy.requiredEdge(b("0.01"), b("0.02"), 30, b("10"), 1000, b("20"));
    assertThat(risky).isGreaterThan(base);
  }

  @Test
  void hedgeComparisonIncludesFeesAndSeparatesRiskReduction() {
    assertThat(
            PairPolicy.hedge(b("0.4"), b("0.5"), b("0.39"), b("0.01"), b("0.01"), b("0.02"), false)
                .action())
        .isEqualTo("COMPLETE");
    assertThat(
            PairPolicy.hedge(b("0.6"), b("0.5"), b("0.59"), b("0.01"), b("0.01"), b("0.02"), false)
                .action())
        .isEqualTo("WAIT");
    assertThat(
            PairPolicy.hedge(b("0.6"), b("0.5"), b("0.59"), b("0.01"), b("0.01"), b("0.02"), true)
                .action())
        .isEqualTo("RISK_SELL");
  }
}
