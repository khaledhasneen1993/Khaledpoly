package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class ExternalPaperSessionTest {
  @TempDir Path dir;
  final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
  final ClosedLoopReplay.VirtualClock clock = new ClosedLoopReplay.VirtualClock();
  final long base = 1800000000000L;
  final String condition = "0x" + "1".repeat(64);
  final AccountLedger.Limits limits =
      new AccountLedger.Limits(b("25"), b("25"), b("100"), b("25"), b("50"));

  BigDecimal b(String n) {
    return new BigDecimal(n);
  }

  JsonNode node(Object n) {
    return mapper.valueToTree(n);
  }

  void seed(ResearchSession session) {
    session.accept(
        "META",
        base,
        node(
            new ResearchMarket(
                condition,
                "a",
                "b",
                base,
                base + 900000,
                b(".01"),
                b("5"),
                b(".07"),
                1,
                true,
                base,
                "fixture")));
    var events = new ArrayList<Map<String, Object>>();
    for (String token : List.of("a", "b"))
      events.add(
          Map.of(
              "kind",
              "BOOK",
              "data",
              Map.of(
                  "token",
                  token,
                  "sourceMs",
                  base + 250,
                  "bids",
                  List.of(Map.of("price", ".4", "size", "100")),
                  "asks",
                  List.of(Map.of("price", ".6", "size", "100")))));
    session.accept("FRAME", base + 250, node(Map.of("events", events)));
  }

  ObjectNode proposal(ResearchSession session, String id) {
    var snapshot = session.researchSnapshot(base + 250);
    var p = mapper.createObjectNode();
    p.put("id", id)
        .put("strategy", "complete-set")
        .put("sessionId", snapshot.path("sessionId").asText())
        .put("accountId", "paper-default")
        .put("sequence", snapshot.path("sequence").asLong());
    var legs = mapper.createArrayNode();
    for (String token : List.of("a", "b"))
      legs.add(
          node(
              Map.of(
                  "condition",
                  condition,
                  "token",
                  token,
                  "buy",
                  true,
                  "price",
                  ".41",
                  "size",
                  "5",
                  "expiresMs",
                  base + 1000)));
    p.set("legs", legs);
    return p;
  }

  JsonNode print(String token, long at, String id, String size) {
    return node(
        Map.of(
            "token",
            token,
            "sourceMs",
            at,
            "side",
            "SELL",
            "price",
            ".41",
            "size",
            size,
            "tradeId",
            id));
  }

  @Test
  void actualMatchingActivationIdempotencyAndMergeAccounting() {
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
      seed(session);
      assertThat(ledger.snapshot().orders()).isEmpty();
      var request = proposal(session, "one");
      session.accept("EXTERNAL_PROPOSAL", base + 251, request);
      assertThat(session.externalReply("one").path("status").asText()).isEqualTo("PAPER_SUBMITTED");
      assertThat(ledger.availableCash()).isEqualByComparingTo("495.90");
      session.accept("EXTERNAL_PROPOSAL", base + 252, request);
      assertThat(session.externalReply("one").path("status").asText())
          .isEqualTo("PAPER_ALREADY_RECORDED");
      assertThat(ledger.snapshot().orders()).hasSize(2);
      session.accept("TRADE", base + 500, print("a", base + 500, "before", "1000"));
      assertThat(ledger.snapshot().holdings()).isEmpty();
      session.accept("TRADE", base + 502, print("a", base + 502, "first", "5"));
      assertThat(ledger.snapshot().holdings().get("a").shares()).isEqualByComparingTo("5");
      session.accept("TRADE", base + 503, print("b", base + 503, "second", "5"));
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("500.89");
      assertThat(ledger.snapshot().realized()).isEqualByComparingTo("0.89");
      assertThat(ledger.snapshot().fees()).isEqualByComparingTo("0.01");
      session.accept("EXTERNAL_PROPOSAL", base + 504, request);
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("500.89");
    }
  }

  @Test
  void partialPrintNeverFillsBothLegsAndExpiredObservationsReject() {
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
      seed(session);
      var request = proposal(session, "one");
      session.accept("EXTERNAL_PROPOSAL", base + 501, request);
      assertThat(session.externalReply("one").path("status").asText()).isEqualTo("PAPER_REJECTED");
      assertThat(ledger.snapshot().orders()).isEmpty();
      var fresh = session.researchSnapshot(base + 502);
      request.put("sequence", fresh.path("sequence").asLong());
      session.accept("EXTERNAL_PROPOSAL", base + 503, request);
      session.accept("TRADE", base + 754, print("a", base + 754, "partial", "1"));
      assertThat(ledger.snapshot().holdings().get("a").shares()).isEqualByComparingTo("1");
      assertThat(
              ledger
                  .snapshot()
                  .holdings()
                  .getOrDefault("b", new AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
                  .shares())
          .isZero();
      assertThat(ledger.snapshot().realized()).isZero();
    }
  }

  @Test
  void batchFailureDoesNotReserveFirstLeg() {
    clock.at = base;
    try (var ledger =
        new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock)) {
      assertThatThrownBy(
              () ->
                  ledger.reserveBatch(
                      List.of(
                          new AccountLedger.OrderIntent("one", "a", true, b(".4"), b("5")),
                          new AccountLedger.OrderIntent("two", "b", true, b(".6"), b("100")))))
          .isInstanceOf(IllegalStateException.class);
      assertThat(ledger.snapshot().orders()).isEmpty();
      assertThat(ledger.availableCash()).isEqualByComparingTo("500");
    }
  }

  @Test
  void ownedTwoSidedQuotesDoNotSelfCrossOrCreditUnfilledSaleCash() {
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
      seed(session);
      ledger.reserve("owned", "a", true, b(".4"), b("5"));
      ledger.fill("seed-fill", "owned", b("5"), b(".4"), BigDecimal.ZERO);
      var request = proposal(session, "cross");
      var legs = (ArrayNode) request.path("legs");
      ((ObjectNode) legs.get(0)).put("price", ".59");
      ((ObjectNode) legs.get(1)).put("token", "a").put("buy", false).put("price", ".41");
      session.accept("EXTERNAL_PROPOSAL", base + 251, request);
      assertThat(session.externalReply("cross").path("status").asText())
          .isEqualTo("PAPER_REJECTED");
      assertThat(ledger.availableCash()).isEqualByComparingTo("498");
      request.put("id", "two-sided").put("strategy", "inventory-mm-shadow");
      ((ObjectNode) legs.get(0)).put("price", ".41");
      ((ObjectNode) legs.get(1)).put("price", ".59");
      session.accept("EXTERNAL_PROPOSAL", base + 252, request);
      assertThat(session.externalReply("two-sided").path("status").asText())
          .isEqualTo("PAPER_SUBMITTED");
      assertThat(ledger.availableCash()).isEqualByComparingTo("495.95");
      assertThat(ledger.snapshot().cash()).isEqualByComparingTo("498");
    }
  }

  @Test
  void externalReplayRestoresRecoveredHoldingsInsteadOfResettingCash() throws Exception {
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
                "old")) {
      seed(session);
      ledger.reserve("owned", "a", true, b(".4"), b("5"));
      ledger.fill("seed-fill", "owned", b("5"), b(".4"), BigDecimal.ZERO);
    }
    clock.at = base + 1000;
    try (var journal =
            new PaperJournal(mapper, clock, dir.resolve("tapes").toString(), "restart", "test");
        var ledger =
            new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var session =
            new ResearchSession(
                ledger,
                ResearchConfig.defaults(),
                mapper,
                dir.resolve("session.json"),
                (k, v) -> journal.record("SESSION_" + k, null, v),
                true,
                "recovered")) {
      journal.record(
          "DATASET_CONFIG",
          null,
          Map.of("format", "normalized-public-v2", "strategyIndependent", false));
      journal.record("RESEARCH_TICK", null, Map.of());
      session.accept("TICK", clock.millis(), node(Map.of()));
      assertThat(session.report().get("halted")).isEqualTo(true);
    }
    Path tape;
    try (var paths = Files.walk(dir.resolve("tapes"))) {
      tape =
          paths
              .filter(p -> p.getFileName().toString().equals("events.jsonl"))
              .findFirst()
              .orElseThrow();
    }
    var replay =
        ClosedLoopReplay.runExternal(
            tape, dir.resolve("audit"), ResearchConfig.defaults(), limits, mapper, false);
    assertThat((BigDecimal) replay.get("cash")).isEqualByComparingTo("498");
    assertThat(((JsonNode) replay.get("startingCash")).decimalValue()).isEqualByComparingTo("498");
    JsonNode holdings = mapper.valueToTree(replay.get("holdings"));
    assertThat(holdings.path("a").path("shares").decimalValue()).isEqualByComparingTo("5");
    assertThat(replay.get("halted")).isEqualTo(true);
    assertThatThrownBy(
            () ->
                ClosedLoopReplay.runExternal(
                    tape,
                    dir.resolve("changed-config"),
                    ResearchConfig.defaults().stress(),
                    limits,
                    mapper,
                    false))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("recovered account");
  }

  @Test
  void sustainedBookUpdatesKeepVolatilityTelemetryBoundedAndReplayReadable() throws Exception {
    clock.at = base;
    var features = new ArrayList<JsonNode>();
    try (var ledger =
            new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var session =
            new ResearchSession(
                ledger,
                ResearchConfig.defaults(),
                mapper,
                dir.resolve("session.json"),
                (k, v) -> {
                  if (k.equals("ORDER_FEATURES")) features.add(node(v));
                },
                true,
                "s")) {
      seed(session);
      var request = proposal(session, "sustained-books");
      for (int i = 251; i <= 1500; i++)
        session.accept(
            "BOOK",
            base + i,
            node(
                Map.of(
                    "token",
                    "a",
                    "sourceMs",
                    base + i,
                    "bids",
                    List.of(Map.of("price", i % 2 == 0 ? ".4" : ".41", "size", "100")),
                    "asks",
                    List.of(Map.of("price", ".6", "size", "100")))));
      var observation = session.researchSnapshot(base + 1500);
      request.put("sequence", observation.path("sequence").asLong());
      for (var leg : request.path("legs")) ((ObjectNode) leg).put("expiresMs", base + 2000);
      session.accept("EXTERNAL_PROPOSAL", base + 1501, request);
      assertThat(session.externalReply("sustained-books").path("status").asText())
          .isEqualTo("PAPER_SUBMITTED");
      assertThat(features).isNotEmpty();
      for (var feature : features) {
        String json = mapper.writeValueAsString(feature);
        assertThat(mapper.readTree(json).path("orderId").asText())
            .isEqualTo(feature.path("orderId").asText());
        assertThat(mapper.readTree(json).path("features").path("volatility").decimalValue())
            .isEqualByComparingTo(feature.path("features").path("volatility").decimalValue());
        assertThat(feature.path("features").path("volatility").decimalValue().scale())
            .isLessThanOrEqualTo(18);
        assertThat(json.length()).isLessThan(2000);
      }
    }
  }

  @Test
  void restartCancelsUnknownQueueAndCannotExecuteSameIdAgain() {
    clock.at = base;
    ObjectNode request;
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
      seed(session);
      request = proposal(session, "one");
      session.accept("EXTERNAL_PROPOSAL", base + 251, request);
    }
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
                "new-session")) {
      assertThat(ledger.availableCash()).isEqualByComparingTo("500");
      session.accept("EXTERNAL_PROPOSAL", base + 300, request);
      assertThat(session.externalReply("one").path("status").asText())
          .isEqualTo("PAPER_ALREADY_RECORDED");
      assertThat(ledger.snapshot().orders()).hasSize(2);
      request.put("strategy", "changed");
      session.accept("EXTERNAL_PROPOSAL", base + 301, request);
      assertThat(session.externalReply("one").path("status").asText()).isEqualTo("PAPER_REJECTED");
      assertThat(ledger.availableCash()).isEqualByComparingTo("500");
    }
  }
}
