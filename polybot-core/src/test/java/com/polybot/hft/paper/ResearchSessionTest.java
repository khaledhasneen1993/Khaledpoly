package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.polybot.hft.risk.AccountLedger;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class ResearchSessionTest {
  @TempDir Path dir;
  final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
  final ClosedLoopReplay.VirtualClock clock = new ClosedLoopReplay.VirtualClock();
  final long base = 1800000000000L;
  final String condition = "0x" + "1".repeat(64);
  final AccountLedger.Limits limits =
      new AccountLedger.Limits(b("25"), b("25"), b("250"), b("25"), b("50"));

  BigDecimal b(String s) {
    return new BigDecimal(s);
  }

  ResearchMarket market() {
    return new ResearchMarket(
        condition,
        "a",
        "b",
        base,
        base + 900000,
        b("0.01"),
        b("1"),
        b("0.07"),
        1,
        true,
        base,
        "https://gamma-api.polymarket.com/markets?slug=fixture");
  }

  JsonNode book(String token, long at, String bid, String ask, String size) {
    return mapper.valueToTree(
        Map.of(
            "token",
            token,
            "sourceMs",
            at,
            "bids",
            List.of(Map.of("price", bid, "size", size)),
            "asks",
            List.of(Map.of("price", ask, "size", size))));
  }

  void input(ResearchSession s, String kind, long offset, JsonNode data) {
    clock.at = base + offset;
    s.accept(kind, clock.at, data);
  }

  void books(ResearchSession s, long offset, String aBid, String aAsk, String bBid, String bAsk) {
    input(s, "BOOK", offset, book("a", base + offset, aBid, aAsk, "100"));
    input(s, "BOOK", offset, book("b", base + offset, bBid, bAsk, "100"));
  }

  void tick(ResearchSession s, long at) {
    input(s, "TICK", at, mapper.createObjectNode());
  }

  void trade(ResearchSession s, String token, String side, String price, String size, long offset) {
    input(
        s,
        "TRADE",
        offset,
        mapper.valueToTree(
            Map.of(
                "token",
                token,
                "side",
                side,
                "price",
                price,
                "size",
                size,
                "sourceMs",
                base + offset,
                "tradeId",
                token + offset)));
  }

  ResearchSession open(AccountLedger l) {
    return new ResearchSession(
        l, ResearchConfig.defaults(), mapper, dir.resolve("session.json"), (k, v) -> {});
  }

  void enter(ResearchSession s) {
    input(s, "META", 0, mapper.valueToTree(market()));
    books(s, 0, "0.4", "0.6", "0.4", "0.6");
    tick(s, 250);
    tick(s, 501);
  }

  @Test
  void sharedStrategyCreatesOrdersFromObservationsAndMergesNetCost() {
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      enter(s);
      assertThat(l.snapshot().orders()).hasSize(2);
      trade(s, "a", "SELL", "0.41", "5", 502);
      trade(s, "b", "SELL", "0.41", "5", 503);
      assertThat(l.snapshot().cash()).isEqualByComparingTo("500.89");
      assertThat(l.snapshot().realized()).isEqualByComparingTo("0.89");
      assertThat((BigDecimal) s.report().get("quantityPairCompletion")).isEqualByComparingTo("1");
      assertThat((List<?>) s.report().get("pairCompletions")).hasSize(1);
    }
  }

  @Test
  void overdueInventoryUsesDelayedDepthAwareFeeAwareRiskSale() {
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      enter(s);
      trade(s, "a", "SELL", "0.41", "5", 502);
      books(s, 30502, "0.30", "0.50", "0.40", "0.80");
      tick(s, 30752);
      books(s, 30753, "0.29", "0.50", "0.40", "0.80");
      tick(s, 31003);
      assertThat(l.snapshot().holdings().get("a").shares()).isEqualByComparingTo("0");
      assertThat(l.snapshot().cash()).isEqualByComparingTo("499.32793");
      assertThat(l.snapshot().fees()).isEqualByComparingTo("0.07207");
      assertThat(s.report().get("halted")).isEqualTo(true);
      assertThat((List<?>) s.report().get("executions")).hasSize(2);
    }
  }

  @Test
  void riskLossCapPreventsForcedUnlimitedExit() {
    ObjectNode cfg = mapper.valueToTree(ResearchConfig.defaults());
    cfg.put("maxExitLoss", "0.01");
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s =
            new ResearchSession(
                l,
                mapper.convertValue(cfg, ResearchConfig.class),
                mapper,
                dir.resolve("session.json"),
                (k, v) -> {})) {
      enter(s);
      trade(s, "a", "SELL", "0.41", "5", 502);
      books(s, 30502, "0.30", "0.50", "0.40", "0.80");
      tick(s, 30752);
      books(s, 30753, "0.29", "0.50", "0.40", "0.80");
      tick(s, 31003);
      assertThat(l.snapshot().holdings().get("a").shares()).isEqualByComparingTo("5");
      assertThat(l.snapshot().fees()).isEqualByComparingTo("0");
    }
  }

  @Test
  void resolutionRequiresTerminalEvidenceAndCreditsCorrectOutcomeSlotExactlyOnce() {
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      enter(s);
      trade(s, "a", "SELL", "0.41", "5", 502);
      ObjectNode r =
          mapper.valueToTree(
              Map.of(
                  "condition_id",
                  condition,
                  "status",
                  "resolved",
                  "transaction_hash",
                  "0x" + "2".repeat(64),
                  "resolved_block",
                  123,
                  "resolved_at",
                  java.time.Instant.ofEpochMilli(base + 1000).toString(),
                  "payouts",
                  List.of(1, 0)));
      input(s, "RESOLUTION", 1000, r);
      input(s, "RESOLUTION", 1001, r);
      assertThat(l.snapshot().cash()).isEqualByComparingTo("502.94");
      assertThat(l.snapshot().holdings().get("a").shares()).isEqualByComparingTo("0");
      r.put("status", "proposed");
      assertThatThrownBy(() -> input(s, "RESOLUTION", 1002, r))
          .isInstanceOf(IllegalArgumentException.class);
    }
  }

  @Test
  void causalOrderingAndIdentityCannotUseFutureMetadata() {
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      var m = (ObjectNode) mapper.valueToTree(market());
      m.put("observedMs", base + 1);
      assertThatThrownBy(() -> input(s, "META", 0, m)).isInstanceOf(IllegalArgumentException.class);
      input(s, "META", 1, mapper.valueToTree(market()));
      assertThatThrownBy(() -> tick(s, 0)).isInstanceOf(IllegalArgumentException.class);
    }
  }

  @Test
  void rawIngestorReplayAndDirectStreamingAreTheSameStateMachine() throws Exception {
    Path tape = dir.resolve("events.jsonl");
    var rows = new ArrayList<Map<String, Object>>();
    java.util.function.BiConsumer<String, Object> add =
        (kind, data) -> {
          long at = clock.millis();
          rows.add(
              Map.of(
                  "schema",
                  1,
                  "seq",
                  rows.size() + 1,
                  "runId",
                  "fixture",
                  "arrivalMs",
                  at,
                  "kind",
                  kind,
                  "data",
                  data));
        };
    clock.at = base;
    add.accept(
        "DATASET_CONFIG", Map.of("format", "normalized-public-v1", "strategyIndependent", true));
    add.accept("RESEARCH_META", market());
    add.accept("RESEARCH_BOOK", book("a", base, "0.4", "0.6", "100"));
    add.accept("RESEARCH_BOOK", book("b", base, "0.4", "0.6", "100"));
    clock.at = base + 250;
    add.accept("RESEARCH_TICK", Map.of());
    clock.at = base + 501;
    add.accept("RESEARCH_TICK", Map.of());
    for (String token : List.of("a", "b")) {
      clock.at++;
      add.accept(
          "RESEARCH_TRADE",
          Map.of(
              "token",
              token,
              "side",
              "SELL",
              "price",
              "0.41",
              "size",
              "5",
              "sourceMs",
              clock.at,
              "tradeId",
              token));
    }
    add.accept("RUN_END", Map.of());
    Files.writeString(
        tape,
        String.join(
                "\n",
                rows.stream()
                    .map(
                        x -> {
                          try {
                            return mapper.writeValueAsString(x);
                          } catch (Exception e) {
                            throw new RuntimeException(e);
                          }
                        })
                    .toList())
            + "\n");
    var report =
        ClosedLoopReplay.run(
            tape, dir.resolve("replay"), ResearchConfig.defaults(), limits, mapper, false);
    assertThat((BigDecimal) report.get("cash")).isEqualByComparingTo("500.89");
    assertThat(report.get("replayMode")).isEqualTo("closed-loop");
    var stress =
        ClosedLoopReplay.run(
            tape, dir.resolve("stress"), ResearchConfig.defaults().stress(), limits, mapper, false);
    assertThat((BigDecimal) stress.get("cash")).isEqualByComparingTo("500");
  }

  @Test
  void makerInventoryReductionCanSellBeforeEmergencyDeadline() {
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      enter(s);
      trade(s, "a", "SELL", "0.41", "5", 502);
      books(s, 6000, "0.30", "0.50", "0.40", "0.80");
      tick(s, 6250);
      books(s, 6251, "0.30", "0.50", "0.40", "0.80");
      tick(s, 6500);
      tick(s, 6751);
      trade(s, "a", "BUY", "0.49", "5", 6752);
      assertThat(l.snapshot().holdings().get("a").shares()).isEqualByComparingTo("0");
      assertThat(l.snapshot().cash()).isEqualByComparingTo("500.40");
    }
  }

  @Test
  void restartNeverResetsSpentRiskExitBudgetOrInventsQueuePriority() {
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      enter(s);
      trade(s, "a", "SELL", "0.41", "5", 502);
    }
    clock.at = base + 20000;
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      assertThat(s.report().get("halted")).isEqualTo(true);
      assertThat((BigDecimal) s.report().get("exitLossUsed")).isEqualByComparingTo("2.5");
      assertThat(l.snapshot().orders().values().stream().filter(o -> o.remaining().signum() > 0))
          .isEmpty();
    }
  }

  @Test
  void rawNormalizerRequiresSnapshotAndDoesNotUseFutureSourceClock() throws Exception {
    var decoder = new RawTapeNormalizer(mapper);
    var kinds = new ArrayList<String>();
    decoder.accept(
        "{\"event_type\":\"price_change\",\"timestamp\":\""
            + base
            + "\",\"price_changes\":[{\"asset_id\":\"a\",\"side\":\"BUY\",\"price\":\"0.4\",\"size\":\"10\"}]}",
        base,
        (k, n) -> kinds.add(k));
    assertThat(kinds).isEmpty();
    kinds.clear();
    var frame =
        mapper
            .createObjectNode()
            .put("event_type", "book")
            .put("asset_id", "a")
            .put("timestamp", Long.toString(base + 1));
    frame.set("bids", mapper.createArrayNode());
    frame.set("asks", mapper.createArrayNode());
    decoder.accept(mapper.writeValueAsString(frame), base, (k, n) -> kinds.add(k));
    assertThat(kinds).containsExactly("GAP");
  }

  @Test
  void extremeMarketPriceAndDelayedTickCannotSubmitNegativePrice() {
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var session = open(l)) {
      input(session, "META", 0, mapper.valueToTree(market()));
      books(session, 0, "0.001", "0.002", "0.998", "0.999");
      tick(session, 250);
      assertThat(l.snapshot().orders()).isEmpty();
      assertThat(l.snapshot().cash()).isEqualByComparingTo("500");
      assertThat((Map<?, ?>) session.report().get("decisionReasons")).isNotEmpty();
    }
  }

  @Test
  void unavailableMarketCancelsEntriesAndPersistsDisabledMetadataWithoutRefreshingItsClock() {
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      enter(s);
      assertThat(l.snapshot().orders()).hasSize(2);
      input(
          s,
          "MARKET_UNAVAILABLE",
          600,
          mapper.createObjectNode().put("condition", condition).put("status", 404));
      tick(s, 900);
      assertThat(l.snapshot().orders().values())
          .allSatisfy(
              o -> {
                assertThat(o.remaining()).isZero();
                assertThat(o.status()).isEqualTo("CANCELED");
              });
      assertThat(l.availableCash()).isEqualByComparingTo("500");
      assertThat(s.markets().getFirst().accepting()).isFalse();
      assertThat(s.markets().getFirst().observedMs()).isEqualTo(base);
      assertThat(s.report().get("halted")).isEqualTo(false);
    }
    try (var l = new AccountLedger(dir.resolve("ledger.json"), mapper, b("500"), limits, clock);
        var s = open(l)) {
      assertThat(s.markets().getFirst().accepting()).isFalse();
      books(s, 1000, "0.4", "0.6", "0.4", "0.6");
      tick(s, 1251);
      assertThat(l.snapshot().orders().values())
          .allSatisfy(
              o -> {
                assertThat(o.remaining()).isZero();
                assertThat(o.status()).isEqualTo("CANCELED");
              });
      assertThat(l.availableCash()).isEqualByComparingTo("500");
    }
  }

  @Test
  void rawCrossedSplitUpdateIsRejectedAndOnlyFullSnapshotRestoresBook() throws Exception {
    var decoder = new RawTapeNormalizer(mapper);
    var kinds = new ArrayList<String>();
    String snapshot =
        "{\"event_type\":\"book\",\"asset_id\":\"a\",\"timestamp\":\""
            + base
            + "\",\"bids\":[{\"price\":\"0.13\",\"size\":\"10\"}],\"asks\":[{\"price\":\"0.14\",\"size\":\"10\"}]}";
    decoder.accept(snapshot, base, (k, n) -> kinds.add(k));
    String cross =
        "{\"event_type\":\"price_change\",\"timestamp\":\""
            + base
            + "\",\"price_changes\":[{\"asset_id\":\"a\",\"side\":\"BUY\",\"price\":\"0.14\",\"size\":\"91\"}]}";
    decoder.accept(cross, base, (k, n) -> kinds.add(k));
    assertThat(kinds).containsExactly("BOOK", "GAP");
    decoder.accept(snapshot, base, (k, n) -> kinds.add(k));
    assertThat(kinds).containsExactly("BOOK", "GAP", "BOOK");
  }
}
