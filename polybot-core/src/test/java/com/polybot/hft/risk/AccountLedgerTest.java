package com.polybot.hft.risk;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.nio.file.*;
import java.time.*;
import java.util.Map;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class AccountLedgerTest {
  @TempDir Path dir;
  final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
  final AccountLedger.Limits limits =
      new AccountLedger.Limits(b("100"), b("200"), b("300"), b("20"), b("30"));

  static BigDecimal b(String value) {
    return new BigDecimal(value);
  }

  AccountLedger open() {
    return new AccountLedger(
        dir.resolve("ledger.json"), mapper, b("100"), limits, Clock.systemUTC());
  }

  @Test
  void reservesCashAndRejectsOvercommit() {
    try (var l = open()) {
      l.reserve("a", "up", true, b("0.5"), b("180"));
      assertThat(l.availableCash()).isEqualByComparingTo("10");
      assertThatThrownBy(() -> l.reserve("b", "down", true, b("0.5"), b("30")))
          .isInstanceOf(IllegalStateException.class);
      l.cancel("a");
      assertThat(l.availableCash()).isEqualByComparingTo("100");
    }
  }

  @Test
  void partialFillCancelAndRestartPreserveCashBasisAndIdempotency() {
    try (var l = open()) {
      l.reserve("a", "up", true, b("0.5"), b("20"));
      assertThat(l.fill("fill-1", "a", b("5"), b("0.48"), b("0.1"))).isTrue();
      assertThat(l.fill("fill-1", "a", b("5"), b("0.48"), b("0.1"))).isFalse();
      assertThat(l.snapshot().cash()).isEqualByComparingTo("97.5");
      assertThat(l.snapshot().holdings().get("up").basis()).isEqualByComparingTo("2.5");
      assertThat(l.availableCash()).isEqualByComparingTo("90");
    }
    try (var l = open()) {
      assertThat(l.snapshot().orders().get("a").remaining()).isEqualByComparingTo("15");
      l.cancel("a");
      assertThat(l.availableCash()).isEqualByComparingTo("97.5");
    }
  }

  @Test
  void sellsUseCostBasisAndCannotOversell() {
    try (var l = open()) {
      l.reserve("buy", "up", true, b("0.5"), b("20"));
      l.fill("f1", "buy", b("20"), b("0.5"), b("0"));
      l.reserve("sell", "up", false, b("0.6"), b("10"));
      assertThatThrownBy(() -> l.reserve("sell2", "up", false, b("0.6"), b("11")))
          .isInstanceOf(IllegalStateException.class);
      l.fill("f2", "sell", b("10"), b("0.6"), b("0.1"));
      assertThat(l.snapshot().realized()).isEqualByComparingTo("0.9");
      assertThat(l.snapshot().holdings().get("up").basis()).isEqualByComparingTo("5");
    }
  }

  @Test
  void dailyLossLatchSurvivesRestart() {
    try (var l = open()) {
      l.reserve("a", "up", true, b("0.5"), b("60"));
      l.fill("f", "a", b("60"), b("0.5"), b("0"));
      l.mark(Map.of("up", b("0")));
      assertThat(l.snapshot().halted()).isTrue();
      assertThatThrownBy(() -> l.reserve("b", "down", true, b("0.5"), b("1")))
          .isInstanceOf(IllegalStateException.class);
    }
    try (var l = open()) {
      assertThat(l.snapshot().halted()).isTrue();
    }
  }

  @Test
  void missingMarksAndBadFillsFailClosed() {
    try (var l = open()) {
      l.reserve("a", "up", true, b("0.5"), b("10"));
      assertThatThrownBy(() -> l.fill("x", "a", b("11"), b("0.5"), b("0")))
          .isInstanceOf(IllegalArgumentException.class);
      l.fill("f", "a", b("1"), b("0.5"), b("0"));
      assertThatThrownBy(() -> l.mark(Map.of())).isInstanceOf(IllegalStateException.class);
    }
  }

  @Test
  void corruptionDoesNotResetAccount() throws Exception {
    Files.writeString(dir.resolve("ledger.json"), "bad");
    assertThatThrownBy(this::open).isInstanceOf(IllegalStateException.class);
  }

  @Test
  void terminalOrderHistorySurvivesRestart() {
    try (var l = open()) {
      l.reserve("done", "up", true, b("0.5"), b("2"));
      l.fill("f", "done", b("2"), b("0.5"), b("0"));
      l.reserve("cancelled", "down", true, b("0.5"), b("4"));
      l.fill("f2", "cancelled", b("1"), b("0.5"), b("0"));
      l.cancel("cancelled");
    }
    try (var l = open()) {
      assertThat(l.snapshot().orders().get("done").status()).isEqualTo("FILLED");
      assertThat(l.snapshot().orders().get("done").filled()).isEqualByComparingTo("2");
      assertThat(l.snapshot().orders().get("cancelled").status()).isEqualTo("CANCELED");
      assertThat(l.snapshot().orders().get("cancelled").filled()).isEqualByComparingTo("1");
    }
  }

  @Test
  void failedPersistenceLatchesUntilRestart() throws Exception {
    try (var l = open()) {
      Files.createDirectory(dir.resolve("ledger.json.tmp"));
      assertThatThrownBy(() -> l.reserve("a", "up", true, b("0.5"), b("2")))
          .isInstanceOf(IllegalStateException.class);
      Files.delete(dir.resolve("ledger.json.tmp"));
      assertThatThrownBy(() -> l.mark(Map.of())).isInstanceOf(IllegalStateException.class);
      assertThat(l.snapshot().orders()).isEmpty();
    }
    try (var l = open()) {
      assertThat(l.availableCash()).isEqualByComparingTo("100");
    }
  }
}
