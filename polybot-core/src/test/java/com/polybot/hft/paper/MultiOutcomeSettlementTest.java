package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.*;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class MultiOutcomeSettlementTest {
  @TempDir Path dir;
  final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
  final ClosedLoopReplay.VirtualClock clock = new ClosedLoopReplay.VirtualClock();
  final long base = 1800000000000L;
  final AccountLedger.Limits limits =
      new AccountLedger.Limits(b("25"), b("25"), b("100"), b("25"), b("50"));

  BigDecimal b(String value) {
    return new BigDecimal(value);
  }

  ResearchMarket market(int i) {
    return new ResearchMarket(
        "0x" + String.valueOf(i + 1).repeat(64),
        "" + (i * 2 + 1),
        "" + (i * 2 + 2),
        base,
        base + 1000,
        b(".01"),
        b("5"),
        b(".07"),
        1,
        true,
        base,
        "fixture",
        true);
  }

  JsonNode resolution(int i) {
    return mapper.valueToTree(
        Map.of(
            "condition_id",
            market(i).condition(),
            "status",
            "resolved",
            "transaction_hash",
            "0x" + "a".repeat(64),
            "resolved_block",
            1,
            "resolved_at",
            Instant.ofEpochMilli(base + 1100).toString(),
            "payouts",
            List.of(i == 1 ? "1" : "0", i == 1 ? "0" : "1")));
  }

  ObjectNode event() {
    var event = mapper.createObjectNode();
    event.put("id", "123").put("closed", true).put("negRisk", true).put("negRiskAugmented", false);
    var rows = mapper.createArrayNode();
    for (int i = 0; i < 3; i++)
      rows.add(
          mapper.valueToTree(
              Map.of(
                  "conditionId",
                  market(i).condition(),
                  "version",
                  "v1",
                  "clobTokenIds",
                  List.of(market(i).first(), market(i).second()),
                  "outcomes",
                  List.of("Yes", "No"),
                  "groupItemTitle",
                  "Candidate " + i)));
    event.set("markets", rows);
    return event;
  }

  void seed(ResearchSession session, AccountLedger ledger) {
    for (int i = 0; i < 3; i++) {
      session.accept("META", base, mapper.valueToTree(market(i)));
      BigDecimal price = b(".2").add(b(".1").multiply(BigDecimal.valueOf(i)));
      ledger.reserve("seed-" + i, market(i).first(), true, price, b("5"));
      ledger.fill("fixture-fill-" + i, "seed-" + i, b("5"), price, BigDecimal.ZERO);
    }
  }

  @Test
  void threeOutcomesRequireAllEvidenceThenOneAtomicRedemption() {
    clock.at = base;
    try (var ledger =
            new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var session =
            new ResearchSession(
                ledger,
                ResearchConfig.defaults(),
                mapper,
                dir.resolve("session.json"),
                (k, v) -> {},
                true,
                "s")) {
      seed(session, ledger);
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("495.50");
      session.accept("RESOLUTION", base + 1200, resolution(0));
      session.accept("RESOLUTION", base + 1200, resolution(1));
      session.accept("GROUP_SETTLEMENT", base + 1201, event());
      assertThat(session.externalReply("settle:123").path("status").asText())
          .isEqualTo("PAPER_GROUP_DEFERRED");
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("495.50");
      session.accept("RESOLUTION", base + 1202, resolution(2));
      var augmented = event();
      augmented.put("negRiskAugmented", true);
      session.accept("GROUP_SETTLEMENT", base + 1203, augmented);
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("495.50");
      session.accept("GROUP_SETTLEMENT", base + 1204, event());
      assertThat(session.externalReply("settle:123").path("status").asText())
          .isEqualTo("PAPER_GROUP_REDEEMED");
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("500.49");
      assertThat(ledger.snapshot().realized()).isEqualByComparingTo(".49");
      assertThat(ledger.snapshot().fees()).isEqualByComparingTo(".01");
      assertThat(ledger.snapshot().holdings().values())
          .allMatch(h -> h.shares().signum() == 0 && h.basis().signum() == 0);
      session.accept("GROUP_SETTLEMENT", base + 1205, event());
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("500.49");
      var changed = event();
      ((ObjectNode) changed.path("markets").get(0)).put("groupItemTitle", "Different name");
      session.accept("GROUP_SETTLEMENT", base + 1206, changed);
      assertThat(session.externalReply("settle:123").path("status").asText())
          .isEqualTo("PAPER_GROUP_DEFERRED");
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("500.49");
    }
  }

  @Test
  void malformedTerminalGroupCannotConsumeAnyInventory() {
    clock.at = base;
    try (var ledger =
        new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock)) {
      assertThatThrownBy(
              () ->
                  ledger.redeemBatch(
                      "group",
                      Map.of("a", Map.of("1", BigDecimal.ONE), "b", Map.of("2", BigDecimal.ZERO)),
                      BigDecimal.ZERO))
          .isInstanceOf(IllegalArgumentException.class);
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("500");
      assertThat(ledger.snapshot().executions()).doesNotContain("group");
    }
  }
}
