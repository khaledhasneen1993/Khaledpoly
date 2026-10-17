package com.polybot.hft.risk;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.time.Clock;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

/** Experimental production-ledger timings, with NO arbitrary runner-specific latency SLO. */
class AccountLedgerPerformanceBaselineTest {
  @TempDir Path dir;
  private final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();

  private static BigDecimal d(String value) {
    return new BigDecimal(value);
  }

  private AccountLedger open() {
    return new AccountLedger(
        dir.resolve("perf-paper-account.json"),
        mapper,
        d("100"),
        new AccountLedger.Limits(d("10"), d("10"), d("60"), d("99"), d("99")),
        Clock.systemUTC());
  }

  static long percentile(List<Long> readings, double p) {
    if (readings.isEmpty()) throw new IllegalArgumentException("Missing performance observations");
    var sorted = new ArrayList<>(readings);
    Collections.sort(sorted);
    int index = Math.min(sorted.size() - 1, (int) Math.ceil(p * sorted.size()) - 1);
    return sorted.get(index) / 1000; // measured microseconds, not a speed guarantee
  }

  @Test
  @Timeout(30)
  void reportsFsyncLedgerAndReopenLatencyOnDurablePaperAccounting() {
    List<Long> reserve = new ArrayList<>();
    List<Long> fill = new ArrayList<>();
    List<Long> reopen = new ArrayList<>();
    BigDecimal expectedCash = d("100");

    for (int i = 0; i < 12; i++) {
      long started = System.nanoTime();
      try (var ledger = open()) {
        reopen.add(System.nanoTime() - started);
        String token = "bench-" + i;

        started = System.nanoTime();
        ledger.reserve("buy-" + i, token, true, d("0.50"), d("2"));
        reserve.add(System.nanoTime() - started);

        started = System.nanoTime();
        assertThat(ledger.fill("buy-exec-" + i, "buy-" + i, d("2"), d("0.50"), d("0.001")))
            .isTrue();
        fill.add(System.nanoTime() - started);

        started = System.nanoTime();
        ledger.reserve("sell-" + i, token, false, d("0.55"), d("2"));
        reserve.add(System.nanoTime() - started);

        started = System.nanoTime();
        assertThat(ledger.fill("sell-exec-" + i, "sell-" + i, d("2"), d("0.55"), d("0.001")))
            .isTrue();
        fill.add(System.nanoTime() - started);

        expectedCash = expectedCash.add(d("0.098"));
        assertThat(ledger.snapshot().cash()).isEqualByComparingTo(expectedCash);
      }
    }
    try (var ledger = open()) {
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("101.176");
      assertThat(ledger.snapshot().realized()).isEqualByComparingTo("1.176");
      assertThat(ledger.snapshot().fees()).isEqualByComparingTo("0.024");
      assertThat(ledger.availableCash()).isEqualByComparingTo("101.176");
    }

    assertThat(reserve).hasSize(24);
    assertThat(fill).hasSize(24);
    assertThat(reopen).hasSize(12);
    System.out.printf(
        "PHASE6_PAPER_LEDGER_BASELINE runner-dependent microseconds: "
            + "reserve_p50=%d reserve_p95=%d fill_p50=%d fill_p95=%d "
            + "reopen_p50=%d reopen_p95=%d; samples=24/24/12; LIVE=false%n",
        percentile(reserve, 0.50),
        percentile(reserve, 0.95),
        percentile(fill, 0.50),
        percentile(fill, 0.95),
        percentile(reopen, 0.50),
        percentile(reopen, 0.95));
  }
}
