package com.polybot.hft.executor.sim;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.config.HftProperties;
import com.polybot.hft.domain.OrderSide;
import com.polybot.hft.events.NoopHftEventPublisher;
import com.polybot.hft.paper.*;
import com.polybot.hft.polymarket.api.*;
import com.polybot.hft.polymarket.gamma.PolymarketGammaClient;
import com.polybot.hft.polymarket.model.*;
import com.polybot.hft.polymarket.service.MarketPolicyService;
import com.polybot.hft.polymarket.ws.*;
import java.math.*;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import java.util.function.BiConsumer;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

class PaperReplayIntegrationTest {
  @TempDir Path dir;

  static class MutableClock extends Clock {
    Instant now = Instant.parse("2026-10-16T12:00:00Z");

    public ZoneId getZone() {
      return ZoneOffset.UTC;
    }

    public Clock withZone(ZoneId z) {
      return this;
    }

    public Instant instant() {
      return now;
    }
  }

  final MutableClock clock = new MutableClock();
  final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
  BiConsumer<String, JsonNode> listener;

  BigDecimal b(String x) {
    return new BigDecimal(x);
  }

  LimitOrderRequest request(String token, String price, String id) {
    return new LimitOrderRequest(
        token,
        OrderSide.BUY,
        b(price),
        b("5"),
        ClobOrderType.GTC,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        id);
  }

  JsonNode depth(String token, String price) {
    return mapper.valueToTree(
        Map.of(
            "token",
            token,
            "sourceMs",
            clock.millis(),
            "bids",
            List.of(Map.of("price", price, "size", "10")),
            "asks",
            List.of(Map.of("price", "0.7", "size", "100"))));
  }

  void trade(String token, String price, String size) {
    listener.accept(
        "TRADE",
        mapper.valueToTree(
            Map.of(
                "token",
                token,
                "sourceMs",
                clock.millis(),
                "price",
                price,
                "size",
                size,
                "side",
                "SELL",
                "tradeId",
                token + clock.millis())));
  }

  record Fixture(PaperExchangeSimulator exchange, PaperJournal journal) implements AutoCloseable {
    public void close() {
      exchange.closeLedger();
      journal.close();
    }
  }

  private Fixture open() {
    var hft = new HftProperties(null, null, null, null, null);
    var sim = new ExecutorSimulationProperties(true, "test", "paper", true);
    var ws = mock(ClobMarketWebSocketClient.class);
    doAnswer(
            a -> {
              listener = a.getArgument(0);
              return null;
            })
        .when(ws)
        .onTape(any());
    when(ws.getTopOfBook(anyString()))
        .thenAnswer(
            a ->
                Optional.of(
                    new TopOfBook(
                        b("0.3"), b("0.7"), b("100"), b("100"), null, clock.instant(), null)));
    var policy = mock(MarketPolicyService.class);
    var c =
        new MarketConstraints(
            "0x" + "1".repeat(64),
            "v2",
            b("0.01"),
            b("1"),
            false,
            clock.instant().plusSeconds(900),
            mapper.createObjectNode());
    when(policy.resolve(anyString())).thenReturn(c);
    when(policy.binaryPair("up", "down")).thenReturn(true);
    var journal =
        new PaperJournal(
            mapper, clock, dir.resolve("tapes").toString(), "executor", "test-revision");
    var exchange =
        new PaperExchangeSimulator(
            hft,
            sim,
            mapper,
            clock,
            new NoopHftEventPublisher(),
            ws,
            new PolymarketGammaClient(
                java.net.URI.create("http://unused.invalid"),
                new com.polybot.hft.polymarket.http.PolymarketHttpTransport(
                    mock(java.net.http.HttpClient.class),
                    mapper,
                    com.polybot.hft.polymarket.http.RequestRateLimiter.noop(),
                    new com.polybot.hft.polymarket.http.RetryPolicy(false, 1, 0, 0)),
                mapper),
            policy,
            journal);
    for (var name :
        List.of(
            "initialCash",
            "maxOrder",
            "maxTokenExposure",
            "maxGrossExposure",
            "dailyLoss",
            "drawdown"))
      ReflectionTestUtils.setField(
          exchange,
          name,
          b(name.equals("initialCash") ? "500" : name.equals("maxGrossExposure") ? "250" : "25"));
    ReflectionTestUtils.setField(exchange, "statePath", dir.resolve("live.json").toString());
    ReflectionTestUtils.setField(exchange, "activationMillis", 100L);
    ReflectionTestUtils.setField(exchange, "cancelMillis", 100L);
    ReflectionTestUtils.setField(exchange, "queueMultiplier", b("2"));
    ReflectionTestUtils.setField(exchange, "mergeCost", b("0.01"));
    ReflectionTestUtils.setField(exchange, "portfolioBudget", b("100"));
    exchange.logSimConfig();
    return new Fixture(exchange, journal);
  }

  @Test
  void streamingAndReplayProduceIdenticalPartialFillsCashAndMergePnl() throws Exception {
    var fixture = open();
    var exchange = fixture.exchange();
    var journal = fixture.journal();
    listener.accept("BOOK", depth("up", "0.4"));
    listener.accept("BOOK", depth("down", "0.5"));
    exchange.placePair(
        new PaperPairRequest(request("up", "0.4", "u"), request("down", "0.5", "d")));
    clock.now = clock.now.plusMillis(101);
    trade("up", "0.4", "22");
    assertThat(exchange.getOrder("u").path("status").asText()).isEqualTo("PARTIALLY_FILLED");
    assertThat(exchange.getOrders(Map.of()).path("data")).hasSize(2);
    clock.now = clock.now.plusMillis(1);
    trade("up", "0.4", "3");
    clock.now = clock.now.plusMillis(1);
    trade("down", "0.5", "25");
    assertThat(exchange.accountState().cash()).isEqualByComparingTo("500.49");
    assertThat(exchange.accountState().realized()).isEqualByComparingTo("0.49");
    assertThat(exchange.paperMetrics().get("quantityPairCompletion")).isEqualTo(b("1.00000000"));
    exchange.closeLedger();
    journal.close();
    Path tape;
    try (var files = Files.walk(dir.resolve("tapes"))) {
      tape =
          files
              .filter(p -> p.getFileName().toString().equals("events.jsonl"))
              .findFirst()
              .orElseThrow();
    }
    var replay = ReplayRunner.run(tape, dir.resolve("replay"), false, mapper);
    assertThat((BigDecimal) replay.get("cash")).isEqualByComparingTo("500.49");
    assertThat((BigDecimal) replay.get("netRealizedPnl")).isEqualByComparingTo("0.49");
    assertThat(replay.get("recordingClosedCleanly")).isEqualTo(true);
    assertThat((List<?>) replay.get("fills")).hasSize(3);
    var stress = ReplayRunner.run(tape, dir.resolve("stress"), true, mapper);
    assertThat((List<?>) stress.get("fills")).isEmpty();
    assertThat(stress.get("decision")).isEqualTo("NO_GO");
  }

  @Test
  void restartRetainsUnhedgedAgeAndHaltsAtDeadline() {
    try (var f = open()) {
      listener.accept("BOOK", depth("up", "0.4"));
      listener.accept("BOOK", depth("down", "0.5"));
      f.exchange()
          .placePair(new PaperPairRequest(request("up", "0.4", "u"), request("down", "0.5", "d")));
      clock.now = clock.now.plusMillis(101);
      trade("up", "0.4", "25");
      assertThat(f.exchange().accountState().holdings().get("up").shares())
          .isEqualByComparingTo("5");
    }
    clock.now = clock.now.plusMillis(29999);
    try (var f = open()) {
      f.exchange().simulateFills();
      assertThat(f.exchange().accountState().halted()).isFalse();
      clock.now = clock.now.plusMillis(1);
      f.exchange().simulateFills();
      assertThat(f.exchange().accountState().halted()).isTrue();
      assertThat(f.exchange().getOrders(Map.of()).path("data")).isEmpty();
      assertThat(f.exchange().availableCash()).isEqualByComparingTo("498");
      assertThatThrownBy(
              () ->
                  f.exchange()
                      .placePair(
                          new PaperPairRequest(
                              request("up", "0.4", "x"), request("down", "0.5", "y"))))
          .isInstanceOf(IllegalStateException.class);
    }
  }
}
