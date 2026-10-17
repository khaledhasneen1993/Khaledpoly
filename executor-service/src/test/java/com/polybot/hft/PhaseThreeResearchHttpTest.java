package com.polybot.hft;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.paper.*;
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
      "paper.market-data.enabled=false", "hft.polymarket.market-ws-enabled=false",
          "hft.events.enabled=false",
      "hft.mode=PAPER", "polybot.executor-token=phase3-test-token-with-32-characters"
    })
@DirtiesContext
class PhaseThreeResearchHttpTest {
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
    Path p = Files.createTempDirectory("phase3-http").resolve("account.json");
    r.add("executor.account.state-path", p::toString);
  }

  void emit(String kind, Object data, long at) {
    clock.at = at;
    ReflectionTestUtils.invokeMethod(feed, "emit", kind, mapper.valueToTree(data));
  }

  ResponseEntity<JsonNode> get(HttpHeaders headers) {
    return client.exchange(
        "/api/research/v1/snapshot", HttpMethod.GET, new HttpEntity<>(headers), JsonNode.class);
  }

  @Test
  void authenticatedAtomicReadOnlySnapshotContract() throws Exception {
    assertThat(get(new HttpHeaders()).getStatusCode().value()).isEqualTo(401);
    var headers = new HttpHeaders();
    headers.set("X-Polybot-Token", "phase3-test-token-with-32-characters");
    assertThat(get(headers).getStatusCode().value()).isEqualTo(503);
    long at = 1800000000000L;
    emit(
        "META",
        new ResearchMarket(
            "0x" + "1".repeat(64),
            "a",
            "b",
            at,
            at + 900000,
            new BigDecimal("0.01"),
            new BigDecimal("5"),
            new BigDecimal("0.07"),
            1,
            true,
            at,
            "fixture"),
        at);
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
                  at + 250,
                  "bids",
                  List.of(Map.of("price", "0.4", "size", "100")),
                  "asks",
                  List.of(Map.of("price", "0.6", "size", "100")))));
    emit("FRAME", Map.of("events", events), at + 250);
    var response = get(headers);
    assertThat(response.getStatusCode().value()).isEqualTo(200);
    assertThat(response.getHeaders().getCacheControl()).isEqualTo("no-store");
    JsonNode snapshot = response.getBody();
    assertThat(snapshot.path("sequence").asInt()).isEqualTo(2);
    assertThat(snapshot.path("books").size()).isEqualTo(2);
    assertThat(snapshot.path("executionEnabled").asBoolean()).isFalse();
    assertThat(snapshot.path("liveAllowed").asBoolean()).isFalse();
    assertThat(snapshot.path("books").path("a").path("receivedMs").asLong()).isEqualTo(at + 250);
    String original = snapshot.path("account").path("cash").asText();
    ((com.fasterxml.jackson.databind.node.ObjectNode) snapshot.path("account")).put("cash", "9999");
    assertThat(get(headers).getBody().path("account").path("cash").asText()).isEqualTo(original);
    assertThat(
            client
                .exchange(
                    "/api/research/v1/snapshot",
                    HttpMethod.POST,
                    new HttpEntity<>(headers),
                    String.class)
                .getStatusCode()
                .value())
        .isEqualTo(405);
    Files.createDirectories(Path.of("target"));
    mapper.writeValue(Path.of("target/phase3-snapshot.json").toFile(), get(headers).getBody());
  }
}
