package com.polybot.hft.risk;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.time.Clock;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

/**
 * Independent cash/basis/fee conservation against the *real* durable PAPER ledger.
 * Restarts repeatedly between account operations and never invents venue fills.
 */
class AccountLedgerAccountingStressTest {
  @TempDir Path dir;
  final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();

  static BigDecimal d(String value) {
    return new BigDecimal(value);
  }

  AccountLedger open() {
    return new AccountLedger(
        dir.resolve("accounting-stress.json"),
        mapper,
        d("100"),
        new AccountLedger.Limits(d("10"), d("10"), d("60"), d("99"), d("99")),
        Clock.systemUTC());
  }

  @Test
  @Timeout(30)
  void twentyDurableRoundTripsConserveCashBasisFeesAndRealizedPnl() {
    BigDecimal expectedCash = d("100");
    BigDecimal expectedRealized = BigDecimal.ZERO;
    BigDecimal expectedFees = BigDecimal.ZERO;

    for (int i = 0; i < 20; i++) {
      String token = "outcome-" + i;
      String buyId = "buy-" + i;
      String sellId = "sell-" + i;

      // A fully executed BUY includes the acquisition fee in cost basis.
      try (AccountLedger ledger = open()) {
        ledger.reserve(buyId, token, true, d("0.50"), d("5"));
        assertThat(ledger.fill("buy-execution-" + i, buyId, d("5"), d("0.50"), d("0.01")))
            .isTrue();
        assertThat(ledger.fill("buy-execution-" + i, buyId, d("5"), d("0.50"), d("0.01")))
            .isFalse();
        expectedCash = expectedCash.subtract(d("2.51"));
        expectedFees = expectedFees.add(d("0.01"));
        assertThat(ledger.snapshot().cash()).isEqualByComparingTo(expectedCash);
        assertThat(ledger.snapshot().holdings().get(token).basis()).isEqualByComparingTo("2.51");
        assertThat(ledger.snapshot().holdings().get(token).shares()).isEqualByComparingTo("5");
        assertThat(ledger.availableCash()).isEqualByComparingTo(expectedCash);
      }

      // Reopened ledger must enforce inventory-only SELL without a fresh buy.
      try (AccountLedger ledger = open()) {
        ledger.reserve(sellId, token, false, d("0.60"), d("5"));
        assertThat(ledger.fill("sell-execution-" + i, sellId, d("5"), d("0.60"), d("0.02")))
            .isTrue();
        assertThat(ledger.fill("sell-execution-" + i, sellId, d("5"), d("0.60"), d("0.02")))
            .isFalse();

        expectedCash = expectedCash.add(d("2.98"));
        expectedRealized = expectedRealized.add(d("0.47"));
        expectedFees = expectedFees.add(d("0.02"));
        assertThat(ledger.snapshot().cash()).isEqualByComparingTo(expectedCash);
        assertThat(ledger.snapshot().realized()).isEqualByComparingTo(expectedRealized);
        assertThat(ledger.snapshot().fees()).isEqualByComparingTo(expectedFees);
        assertThat(ledger.snapshot().holdings().get(token).shares()).isEqualByComparingTo("0");
        assertThat(ledger.snapshot().holdings().get(token).basis()).isEqualByComparingTo("0");
        assertThat(ledger.availableCash()).isEqualByComparingTo(expectedCash);
      }
    }

    // 20 × (3.00 proceeds - .02 sell fee - 2.50 cost - .01 buy fee)
    // = 9.40 realized PAPER-only profit, never a live performance claim.
    try (AccountLedger ledger = open()) {
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("109.40");
      assertThat(ledger.snapshot().realized()).isEqualByComparingTo("9.40");
      assertThat(ledger.snapshot().fees()).isEqualByComparingTo("0.60");
      assertThat(ledger.availableCash()).isEqualByComparingTo("109.40");
      assertThat(ledger.snapshot().executions()).hasSize(40);
      assertThat(ledger.snapshot().orders()).hasSize(40);
      assertThat(ledger.snapshot().holdings()).hasSize(20);
    }
  }
}
