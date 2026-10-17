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
    assertThat(
            client
                .exchange(
                    "/api/research/v1/proposals/screen",
                    HttpMethod.POST,
                    new HttpEntity<>(" ".repeat(65537), headers),
                    String.class)
                .getStatusCode()
                .value())
        .isEqualTo(413);
    var proposal = mapper.createObjectNode();
    proposal
        .put("id", "http-contract")
        .put("strategy", "external-test")
        .put("sessionId", snapshot.path("sessionId").asText())
        .put("accountId", "paper-default")
        .put("sequence", 2);
    var legs = mapper.createArrayNode();
    legs.add(
        mapper.valueToTree(
            Map.of(
                "condition",
                "0x" + "1".repeat(64),
                "token",
                "a",
                "buy",
                true,
                "price",
                "0.41",
                "size",
                "5",
                "expiresMs",
                at + 400)));
    proposal.set("legs", legs);
    // Remove strategy orders through the feed; the generation must be refreshed before screening.
    emit("GAP", Map.of(), at + 251);
    emit("FRAME", Map.of("events", events), at + 252);
    var current = get(headers).getBody();
    proposal.put("sequence", current.path("sequence").asLong());
    var screened =
        client.exchange(
            "/api/research/v1/proposals/screen",
            HttpMethod.POST,
            new HttpEntity<>(proposal, headers),
            JsonNode.class);
    assertThat(screened.getStatusCode().value()).isEqualTo(200);
    assertThat(screened.getBody().path("executionEnabled").asBoolean()).isFalse();
    assertThat(get(headers).getBody().path("account")).isEqualTo(current.path("account"));
    var repeated =
        client.exchange(
            "/api/research/v1/proposals/screen",
            HttpMethod.POST,
            new HttpEntity<>(proposal, headers),
            JsonNode.class);
    assertThat(repeated.getBody()).isEqualTo(screened.getBody());
    // A lost POST response must be recoverable read-only even when the
    // PAPER executor advances its causal sequence. No duplicate budget
    // reservation, account state change, or new proposal ID is needed.
    var receiptUrl = "/api/research/v1/proposals/screen-receipts/http-contract";
    assertThat(
            client.exchange(receiptUrl, HttpMethod.GET,
                            new HttpEntity<>(new HttpHeaders()), JsonNode.class)
                .getStatusCode().value())
        .isEqualTo(401);
    var savedReceipt = client.exchange(
        receiptUrl, HttpMethod.GET, new HttpEntity<>(headers), JsonNode.class);
    assertThat(savedReceipt.getStatusCode().value()).isEqualTo(200);
    assertThat(savedReceipt.getBody()).isEqualTo(screened.getBody());
    assertThat(savedReceipt.getHeaders().getCacheControl()).isEqualTo("no-store");
    emit("FRAME", Map.of("events", events), at + 253);
    var newerSnapshot = get(headers).getBody();
    assertThat(newerSnapshot.path("sequence").asLong())
        .isGreaterThan(current.path("sequence").asLong());
    var recovered = client.exchange(
        receiptUrl, HttpMethod.GET, new HttpEntity<>(headers), JsonNode.class);
    assertThat(recovered.getStatusCode().value()).isEqualTo(200);
    assertThat(recovered.getBody()).isEqualTo(screened.getBody());
    assertThat(get(headers).getBody().path("account")).isEqualTo(current.path("account"));
    assertThat(
            client.exchange("/api/research/v1/proposals/screen-receipts/no-such-id",
                            HttpMethod.GET,new HttpEntity<>(headers),JsonNode.class)
                .getStatusCode().value())
        .isEqualTo(404);
    proposal.put("sequence", 1);
    assertThat(
            client
                .exchange(
                    "/api/research/v1/proposals/screen",
                    HttpMethod.POST,
                    new HttpEntity<>(proposal, headers),
                    String.class)
                .getStatusCode()
                .value())
        .isEqualTo(409);
    Files.createDirectories(Path.of("target"));
    // Keep the original frame-level contract (before the screening-only exercise).
    ((com.fasterxml.jackson.databind.node.ObjectNode) snapshot.path("account"))
        .put("cash", original);
    mapper.writeValue(Path.of("target/phase3-snapshot.json").toFile(), snapshot);
  }
}
