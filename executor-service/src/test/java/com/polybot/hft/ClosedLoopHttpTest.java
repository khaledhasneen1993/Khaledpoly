package com.polybot.hft;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.paper.*;
import java.math.*;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.*;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.context.annotation.*;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.*;
import org.springframework.test.util.ReflectionTestUtils;

@SpringBootTest(
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = {
      "executor.sim.enabled=true",
      "paper.closed-loop.enabled=true",
      "paper.market-data.enabled=false",
      "hft.polymarket.market-ws-enabled=false",
      "hft.events.enabled=false",
      "hft.mode=PAPER"
    })
@DirtiesContext
class ClosedLoopHttpTest {
  @TestConfiguration
  static class Time {
    @Bean
    @Primary
    ClosedLoopReplay.VirtualClock testClock() {
      return new ClosedLoopReplay.VirtualClock();
    }
  }

  @Autowired TestRestTemplate client;
  @Autowired ResearchFeed feed;
  @Autowired ObjectMapper mapper;
  @Autowired ClosedLoopReplay.VirtualClock clock;

  @DynamicPropertySource
  static void state(DynamicPropertyRegistry r) throws Exception {
    Path p = Files.createTempDirectory("closed-loop-http").resolve("account.json");
    r.add("executor.account.state-path", p::toString);
  }

  void emit(String kind, Object data, long at) {
    clock.at = at;
    ReflectionTestUtils.invokeMethod(feed, "emit", kind, mapper.valueToTree(data));
  }

  @Test
  void actualExecutorRunsSharedStrategyAndProtectsAccountFromLegacyOrderPath() {
    long at = 1800000000000L;
    var m =
        new ResearchMarket(
            "0x" + "1".repeat(64),
            "a",
            "b",
            at,
            at + 900000,
            new BigDecimal("0.01"),
            BigDecimal.ONE,
            new BigDecimal("0.07"),
            1,
            true,
            at,
            "https://gamma-api.polymarket.com/markets?slug=fixture");
    emit("META", m, at);
    for (String token : List.of("a", "b"))
      emit(
          "BOOK",
          Map.of(
              "token",
              token,
              "sourceMs",
              at,
              "bids",
              List.of(Map.of("price", "0.4", "size", "100")),
              "asks",
              List.of(Map.of("price", "0.6", "size", "100"))),
          at);
    emit("TICK", Map.of(), at + 250);
    emit("TICK", Map.of(), at + 501);
    for (String token : List.of("a", "b"))
      emit(
          "TRADE",
          Map.of(
              "token",
              token,
              "sourceMs",
              at + 502,
              "side",
              "SELL",
              "price",
              "0.41",
              "size",
              "5",
              "tradeId",
              token),
          at + 502);
    JsonNode ledger = client.getForObject("/api/polymarket/paper-ledger", JsonNode.class);
    assertThat(ledger.path("cash").decimalValue()).isEqualByComparingTo("500.89");
    JsonNode metrics = client.getForObject("/api/polymarket/paper-metrics", JsonNode.class);
    assertThat(metrics.path("executions")).hasSize(2);
    assertThat(metrics.path("pairCompletions")).hasSize(1);
    var rejected = client.postForEntity("/api/polymarket/paper-pairs", Map.of(), String.class);
    assertThat(rejected.getStatusCode().is2xxSuccessful()).isFalse();
  }
}
