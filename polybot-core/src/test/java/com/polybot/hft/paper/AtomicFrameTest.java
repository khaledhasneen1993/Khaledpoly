package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class AtomicFrameTest {
  @TempDir Path dir;
  final ResearchSessionTest h = new ResearchSessionTest();
  final ObjectMapper m = h.mapper;

  JsonNode frame(JsonNode... books) {
    var events = m.createArrayNode();
    for (var book : books) events.add(m.createObjectNode().put("kind", "BOOK").set("data", book));
    return m.createObjectNode().set("events", events);
  }

  @Test
  void pairedUpdateCannotEnterAgainstHalfUpdatedMarket() {
    h.dir = dir;
    try (var l = new AccountLedger(dir.resolve("ledger.json"), m, h.b("500"), h.limits, h.clock);
        var s = h.open(l)) {
      h.input(s, "META", 0, m.valueToTree(h.market()));
      h.books(s, 0, "0.67", "0.68", "0.32", "0.33");
      h.input(
          s,
          "FRAME",
          250,
          frame(
              h.book("a", h.base + 250, "0.64", "0.68", "159"),
              h.book("b", h.base + 250, "0.35", "0.36", "159")));
      assertThat(l.snapshot().orders()).isEmpty();
      assertThat(((Map<?, ?>) s.report().get("decisionReasons")).containsKey("PAIR_SUBMITTED"))
          .isFalse();
      // The regression is meaningful: the same first leg delivered alone admits the mixed quote.
    }
    try (var l =
            new AccountLedger(dir.resolve("legacy-ledger.json"), m, h.b("500"), h.limits, h.clock);
        var s =
            new ResearchSession(
                l, ResearchConfig.defaults(), m, dir.resolve("legacy-state.json"), (k, v) -> {})) {
      h.input(s, "META", 0, m.valueToTree(h.market()));
      h.books(s, 0, "0.67", "0.68", "0.32", "0.33");
      h.input(s, "BOOK", 250, h.book("a", h.base + 250, "0.64", "0.68", "159"));
      assertThat(l.snapshot().orders()).hasSize(2);
    }
  }

  @Test
  void rawAndNormalizedUseRecordedAvailabilityAndTicksAndHaveIdenticalAudits() throws Exception {
    var rows = new ArrayList<Map<String, Object>>();
    var normalizer = new RawTapeNormalizer(m);
    java.util.function.BiConsumer<String, Object> add =
        (k, d) ->
            rows.add(
                Map.of(
                    "schema",
                    1,
                    "runId",
                    "fixture",
                    "seq",
                    rows.size() + 1,
                    "arrivalMs",
                    h.clock.millis(),
                    "kind",
                    k,
                    "data",
                    d));
    h.clock.at = h.base;
    add.accept(
        "DATASET_CONFIG", Map.of("format", "normalized-public-v2", "strategyIndependent", true));
    add.accept("RESEARCH_META", h.market());
    String books =
        m.writeValueAsString(
            List.of(
                Map.of(
                    "event_type",
                    "book",
                    "asset_id",
                    "a",
                    "timestamp",
                    h.base + 1,
                    "bids",
                    List.of(Map.of("price", "0.4", "size", "100")),
                    "asks",
                    List.of(Map.of("price", "0.6", "size", "100"))),
                Map.of(
                    "event_type",
                    "book",
                    "asset_id",
                    "b",
                    "timestamp",
                    h.base + 1,
                    "bids",
                    List.of(Map.of("price", "0.4", "size", "100")),
                    "asks",
                    List.of(Map.of("price", "0.6", "size", "100")))));
    h.clock.at = h.base + 1;
    add.accept("RAW_MARKET", Map.of("frameId", 1, "text", books));
    h.clock.at = h.base + 5;
    add.accept("RESEARCH_TICK", Map.of());
    var events = m.createArrayNode();
    normalizer.accept(
        books,
        h.base + 10,
        (k, n) -> events.add(m.createObjectNode().put("kind", k).set("data", n)));
    h.clock.at = h.base + 10;
    add.accept("RESEARCH_FRAME", Map.of("frameId", 1, "events", events));
    h.clock.at = h.base + 251;
    add.accept("RESEARCH_TICK", Map.of());
    h.clock.at = h.base + 501;
    add.accept("RESEARCH_TICK", Map.of());
    String trades =
        m.writeValueAsString(
            List.of(
                Map.of(
                    "event_type",
                    "last_trade_price",
                    "asset_id",
                    "a",
                    "timestamp",
                    h.base + 502,
                    "price",
                    "0.41",
                    "size",
                    "5",
                    "side",
                    "SELL"),
                Map.of(
                    "event_type",
                    "last_trade_price",
                    "asset_id",
                    "b",
                    "timestamp",
                    h.base + 502,
                    "price",
                    "0.41",
                    "size",
                    "5",
                    "side",
                    "SELL")));
    h.clock.at = h.base + 502;
    add.accept("RAW_MARKET", Map.of("frameId", 2, "text", trades));
    h.clock.at = h.base + 503;
    add.accept("RESEARCH_TICK", Map.of());
    var prints = m.createArrayNode();
    normalizer.accept(
        trades,
        h.base + 505,
        (k, n) -> prints.add(m.createObjectNode().put("kind", k).set("data", n)));
    h.clock.at = h.base + 505;
    add.accept("RESEARCH_FRAME", Map.of("frameId", 2, "events", prints));
    h.clock.at = h.base + 506;
    add.accept("RUN_END", Map.of("complete", true));
    var tape = dir.resolve("events.jsonl");
    var text = new StringBuilder();
    for (var row : rows) text.append(m.writeValueAsString(row)).append('\n');
    Files.writeString(tape, text);
    var a =
        ClosedLoopReplay.run(
            tape, dir.resolve("normal"), ResearchConfig.defaults(), h.limits, m, false);
    var b =
        ClosedLoopReplay.run(
            tape, dir.resolve("raw"), ResearchConfig.defaults(), h.limits, m, true);
    assertThat((BigDecimal) a.get("cash")).isEqualByComparingTo("500.89");
    for (var key :
        List.of(
            "cash",
            "netRealizedPnl",
            "dataGaps",
            "decisionReasons",
            "executions",
            "frameAtomicity",
            "decisionClock")) assertThat(b.get(key)).as(key).isEqualTo(a.get(key));
    assertThat(Files.readAllLines(dir.resolve("raw/audit.jsonl")))
        .isEqualTo(Files.readAllLines(dir.resolve("normal/audit.jsonl")));
    var compressed = dir.resolve("events.jsonl.gz");
    try (var zipped = new java.util.zip.GZIPOutputStream(Files.newOutputStream(compressed))) {
      zipped.write(text.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
    var zippedReport = ClosedLoopReplay.run(compressed,dir.resolve("gzip"),ResearchConfig.defaults(),h.limits,m,true);
    assertThat(zippedReport.get("executions")).isEqualTo(b.get("executions"));
    assertThat(zippedReport.get("cash")).isEqualTo(b.get("cash"));
    assertThat(Files.readAllLines(dir.resolve("gzip/audit.jsonl"))).isEqualTo(Files.readAllLines(dir.resolve("raw/audit.jsonl")));
    // Crossing a holdout boundary preserves the raw/frame binding and excludes pre-window actions.
    ClosedLoopReplay.run(
        tape,
        dir.resolve("slice"),
        ResearchConfig.defaults(),
        h.limits,
        m,
        true,
        h.base + 5,
        h.base + 504,
        "fixture");
    var trailing =
        Map.of(
            "schema",
            1,
            "runId",
            "fixture",
            "seq",
            rows.size() + 1,
            "arrivalMs",
            h.base + 507,
            "kind",
            "RESEARCH_TICK",
            "data",
            Map.of());
    Files.writeString(tape, text.toString() + m.writeValueAsString(trailing) + "\n");
    assertThatThrownBy(
            () ->
                ClosedLoopReplay.run(
                    tape, dir.resolve("trailing"), ResearchConfig.defaults(), h.limits, m, false))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("after RUN_END");
    // Missing frame boundaries must fail, even if RUN_END claims completion.
    // Explicitly remove the frame row, independent of JSON map field ordering.
    var broken = rows.stream().filter(x -> !x.get("kind").equals("RESEARCH_FRAME")).toList();
    var badText = new StringBuilder();
    int seq = 0;
    for (var row : broken) {
      var copy = new HashMap<>(row);
      copy.put("seq", ++seq);
      badText.append(m.writeValueAsString(copy)).append('\n');
    }
    Files.writeString(tape, badText);
    assertThatThrownBy(
            () ->
                ClosedLoopReplay.run(
                    tape, dir.resolve("broken"), ResearchConfig.defaults(), h.limits, m, true))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("frame");
  }
}
