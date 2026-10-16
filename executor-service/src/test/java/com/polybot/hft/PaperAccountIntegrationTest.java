package com.polybot.hft;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.JsonNode;
import java.nio.file.Files;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest(
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = {
      "executor.sim.enabled=true",
      "executor.sim.fills-enabled=false",
      "hft.mode=PAPER",
      "hft.events.enabled=false",
      "hft.polymarket.market-ws-enabled=false",
      "executor.account.initial-cash=500",
      "polybot.executor-token=test-token"
    })
class PaperAccountIntegrationTest {
  @Autowired TestRestTemplate client;

  @DynamicPropertySource
  static void state(DynamicPropertyRegistry registry) throws Exception {
    var path = Files.createTempDirectory("polybot-http-test").resolve("account.json");
    registry.add("executor.account.state-path", path::toString);
  }

  @Test
  void accountApiIsAuthenticatedAndReportsSpendableCash() {
    assertThat(
            client
                .getForEntity("/api/polymarket/paper-ledger", String.class)
                .getStatusCode()
                .value())
        .isEqualTo(401);
    var headers = new org.springframework.http.HttpHeaders();
    headers.set("X-Polybot-Token", "test-token");
    var response =
        client.exchange(
            "/api/polymarket/bankroll",
            org.springframework.http.HttpMethod.GET,
            new org.springframework.http.HttpEntity<>(headers),
            JsonNode.class);
    assertThat(response.getStatusCode().value()).isEqualTo(200);
    assertThat(response.getBody().path("usdcBalance").decimalValue()).isEqualByComparingTo("500");
    assertThat(response.getBody().path("totalEquityUsd").decimalValue())
        .isEqualByComparingTo("500");
  }
}
