package com.polybot.hft;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.paper.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.*;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.context.annotation.*;
import org.springframework.http.*;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.*;
import org.springframework.test.util.ReflectionTestUtils;

@SpringBootTest(
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = {
      "executor.sim.enabled=true", "paper.closed-loop.enabled=true", "paper.phase3.enabled=true",
          "paper.phase3.execution.enabled=true",
      "paper.market-data.enabled=false", "hft.polymarket.market-ws-enabled=false",
          "hft.events.enabled=false", "hft.mode=PAPER",
      "polybot.executor-token=phase3-execution-test-token-32-characters"
    })
@DirtiesContext
class ExternalPaperHttpTest {
  @TestConfiguration
  static class Time {
    @Bean
    @Primary
    ClosedLoopReplay.VirtualClock externalTestClock() {
      return new ClosedLoopReplay.VirtualClock();
    }
  }

  @Autowired TestRestTemplate client;
  @Autowired ResearchFeed feed;
  @Autowired PaperJournal journal;
  @Autowired ObjectMapper mapper;
  @Autowired ClosedLoopReplay.VirtualClock clock;
  final RawTapeNormalizer normalizer = new RawTapeNormalizer(new ObjectMapper());
  final long base = 1800000000000L;
  final String condition = "0x" + "1".repeat(64);
  long frame;
  static Path root;

  @DynamicPropertySource
  static void state(DynamicPropertyRegistry properties) throws Exception {
    root = Files.createTempDirectory("external-paper-http");
    properties.add("executor.account.state-path", () -> root.resolve("account.json").toString());
    properties.add("paper.record.directory", () -> root.resolve("ingestor").toString());
  }

  HttpHeaders headers() {
    var h = new HttpHeaders();
    h.set("X-Polybot-Token", "phase3-execution-test-token-32-characters");
    return h;
  }

  void emit(String kind, Object data, long at) {
    clock.at = at;
    ReflectionTestUtils.invokeMethod(feed, "emit", kind, mapper.valueToTree(data));
  }

  void raw(Object payload, long at) throws Exception {
    clock.at = at;
    String text = mapper.valueToTree(payload).toString();
    long id = ++frame;
    journal.record("RAW_MARKET", null, Map.of("text", text, "frameId", id));
    var events = mapper.createArrayNode();
    normalizer.accept(
        text,
        at,
        (kind, data) -> {
          var n = mapper.createObjectNode();
          n.put("kind", kind);
          n.set("data", data);
          events.add(n);
        });
    emit("FRAME", Map.of("frameId", id, "events", events), at);
  }

  Map<String, Object> book(String token, long at) {
    return Map.of(
        "event_type",
        "book",
        "asset_id",
        token,
        "timestamp",
        "" + at,
        "bids",
        List.of(Map.of("price", ".4", "size", "100")),
        "asks",
        List.of(Map.of("price", ".6", "size", "100")));
  }

  JsonNode snapshot() {
    return client
        .exchange(
            "/api/research/v1/snapshot",
            HttpMethod.GET,
            new HttpEntity<>(headers()),
            JsonNode.class)
        .getBody();
  }

  ResponseEntity<JsonNode> submit(JsonNode request) {
    return client.exchange(
        "/api/research/v1/proposals/paper",
        HttpMethod.POST,
        new HttpEntity<>(request, headers()),
        JsonNode.class);
  }

  @Test
  void httpExecutesVirtualOrdersAndBothPublicReplayPathsMatchLedger() throws Exception {
    clock.at = base;
    journal.record(
        "DATASET_CONFIG",
        null,
        Map.of("schema", 1, "format", "normalized-public-v2", "strategyIndependent", false));
    emit(
        "META",
        new ResearchMarket(
            condition,
            "a",
            "b",
            base,
            base + 900000,
            new BigDecimal(".01"),
            new BigDecimal("5"),
            new BigDecimal(".07"),
            1,
            true,
            base,
            "fixture"),
        base);
    raw(List.of(book("a", base + 250), book("b", base + 250)), base + 250);
    raw(List.of(book("a", base + 251), book("b", base + 251)), base + 251);
    var observation = snapshot();
    assertThat(observation.path("paperExecutionEnabled").asBoolean()).isTrue();
    var request = mapper.createObjectNode();
    request
        .put("id", "http-execution")
        .put("strategy", "complete-set")
        .put("sessionId", observation.path("sessionId").asText())
        .put("accountId", "paper-default")
        .put("sequence", observation.path("sequence").asLong());
    var legs = mapper.createArrayNode();
    for (String token : List.of("a", "b"))
      legs.add(
          mapper.valueToTree(
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
    request.set("legs", legs);
    clock.at = base + 252;
    var ack = submit(request);
    assertThat(ack.getStatusCode().value()).isEqualTo(200);
    assertThat(ack.getBody().path("status").asText()).isEqualTo("PAPER_SUBMITTED");
    assertThat(ack.getBody().path("orders")).hasSize(2);
    clock.at = base + 253;
    assertThat(submit(request).getBody().path("status").asText())
        .isEqualTo("PAPER_ALREADY_RECORDED");
    for (String token : List.of("a", "b")) {
      long at = base + (token.equals("a") ? 503 : 504);
      raw(
          Map.of(
              "event_type",
              "last_trade_price",
              "asset_id",
              token,
              "timestamp",
              "" + at,
              "price",
              ".41",
              "size",
              "5",
              "side",
              "SELL"),
          at);
    }
    // A clean markout fixture must maintain depth continuity, not silently jump 5s.
    // Production GAP/stale censoring is tested separately in PaperMetricsTest.
    for (long offset : new long[] {1000, 2000, 3000, 4000, 5000, 5504})
      raw(List.of(book("a", base + offset), book("b", base + offset)), base + offset);
    var result = snapshot();
    assertThat(result.path("account").path("cash").decimalValue()).isEqualByComparingTo("500.89");
    journal.close();
    Path tape;
    try (var paths = Files.walk(root.resolve("ingestor"))) {
      tape =
          paths
              .filter(p -> p.getFileName().toString().equals("events.jsonl"))
              .findFirst()
              .orElseThrow();
    }
    var limits =
        new AccountLedger.Limits(
            new BigDecimal("25"),
            new BigDecimal("25"),
            new BigDecimal("250"),
            new BigDecimal("25"),
            new BigDecimal("50"));
    var normalized =
        new LinkedHashMap<>(
            ClosedLoopReplay.runExternal(
                tape,
                root.resolve("normalized"),
                ResearchConfig.defaults(),
                limits,
                mapper,
                false));
    var rawReport =
        new LinkedHashMap<>(
            ClosedLoopReplay.runExternal(
                tape, root.resolve("raw"), ResearchConfig.defaults(), limits, mapper, true));
    assertThat(normalized.get("cash"))
        .isEqualTo(result.path("account").path("cash").decimalValue());
    normalized.remove("inputFormat");
    rawReport.remove("inputFormat");
    assertThat((JsonNode) mapper.valueToTree(rawReport)).isEqualTo(mapper.valueToTree(normalized));
    assertThat(normalized.get("strategyIndependentDataset")).isEqualTo(false);
    assertThat(normalized.get("decision")).isEqualTo("NO_GO");
    assertThat(normalized.get("markoutSamples")).isEqualTo(Map.of(1000, 2, 5000, 2));
    Files.createDirectories(Path.of("target"));
    Files.copy(
        tape, Path.of("target/phase3-execution-events.jsonl"), StandardCopyOption.REPLACE_EXISTING);
  }
}
