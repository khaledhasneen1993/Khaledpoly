package com.polybot.hft.risk;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.time.Clock;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

/**
 * Concurrent PAPER ledger invariants on the actual durable Java account writer.
 * Nothing in this test can place venue orders or connect a wallet.
 */
class AccountLedgerConcurrencyTest {
  @TempDir Path dir;
  private final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();

  private static BigDecimal d(String x) {
    return new BigDecimal(x);
  }

  private AccountLedger open(BigDecimal cap) {
    return new AccountLedger(
        dir.resolve("paper-concurrency-ledger.json"),
        mapper,
        d("100"),
        new AccountLedger.Limits(d("10"), d("10"), cap, d("99"), d("99")),
        Clock.systemUTC());
  }

  @Test
  @Timeout(30)
  void contendingAtomicBatchesDoNotCreateOneSidedReservationsOrSpendTwice()
      throws Exception {
    final int proposals = 32;
    ExecutorService pool = Executors.newFixedThreadPool(8);
    AtomicInteger accepted = new AtomicInteger();
    AtomicInteger rejected = new AtomicInteger();
    List<Future<?>> futures = new ArrayList<>();
    try (AccountLedger ledger = open(d("12"))) {
      CountDownLatch start = new CountDownLatch(1);
      for (int i = 0; i < proposals; i++) {
        int index = i;
        futures.add(
            pool.submit(
                () -> {
                  try {
                    start.await();
                    ledger.reserveBatch(
                        List.of(
                            new AccountLedger.OrderIntent(
                                "up-order-" + index, "up-" + index, true, d("0.5"), d("1")),
                            new AccountLedger.OrderIntent(
                                "down-order-" + index, "down-" + index, true, d("0.5"), d("1"))));
                    accepted.incrementAndGet();
                  } catch (IllegalStateException e) {
                    rejected.incrementAndGet();
                  } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new RuntimeException(e);
                  }
                }));
      }
      start.countDown();
      for (Future<?> future : futures) future.get(25, TimeUnit.SECONDS);

      assertThat(accepted.get()).isEqualTo(12);
      assertThat(rejected.get()).isEqualTo(proposals - 12);
      assertThat(ledger.snapshot().orders()).hasSize(24);
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("100");
      assertThat(ledger.availableCash()).isEqualByComparingTo("88");
      for (int i = 0; i < proposals; i++) {
        boolean up = ledger.snapshot().orders().containsKey("up-order-" + i);
        boolean down = ledger.snapshot().orders().containsKey("down-order-" + i);
        assertThat(up).as("batch %s atomic", i).isEqualTo(down);
      }
    } finally {
      pool.shutdownNow();
    }
    try (AccountLedger restarted = open(d("12"))) {
      assertThat(restarted.snapshot().orders()).hasSize(24);
      assertThat(restarted.availableCash()).isEqualByComparingTo("88");
      assertThat(restarted.snapshot().cash()).isEqualByComparingTo("100");
    }
  }

  @Test
  @Timeout(30)
  void duplicateConcurrentFillReceiptsDebitOnlyOnceEvenAfterRestart()
      throws Exception {
    ExecutorService pool = Executors.newFixedThreadPool(8);
    List<Future<Boolean>> attempts = new ArrayList<>();
    try (AccountLedger ledger = open(d("60"))) {
      ledger.reserve("entry", "up", true, d("0.5"), d("20"));
      CountDownLatch start = new CountDownLatch(1);
      for (int i = 0; i < 24; i++) {
        attempts.add(
            pool.submit(
                () -> {
                  start.await();
                  return ledger.fill("same-execution", "entry", d("5"), d("0.48"), d("0.10"));
                }));
      }
      start.countDown();
      int applied = 0;
      for (Future<Boolean> attempt : attempts)
        if (attempt.get(25, TimeUnit.SECONDS)) applied++;
      assertThat(applied).isEqualTo(1);
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("97.5");
      assertThat(ledger.snapshot().fees()).isEqualByComparingTo("0.10");
      assertThat(ledger.snapshot().holdings().get("up").shares()).isEqualByComparingTo("5");
      assertThat(ledger.snapshot().holdings().get("up").basis()).isEqualByComparingTo("2.5");
      assertThat(ledger.availableCash()).isEqualByComparingTo("90");
    } finally {
      pool.shutdownNow();
    }
    try (AccountLedger restarted = open(d("60"))) {
      assertThat(
              restarted.fill(
                  "same-execution", "entry", d("5"), d("0.48"), d("0.10")))
          .isFalse();
      assertThat(restarted.snapshot().cash()).isEqualByComparingTo("97.5");
      assertThat(restarted.snapshot().fees()).isEqualByComparingTo("0.10");
      assertThat(restarted.snapshot().executions()).containsExactly("same-execution");
      restarted.cancel("entry");
      assertThat(restarted.availableCash()).isEqualByComparingTo("97.5");
    }
  }
}
