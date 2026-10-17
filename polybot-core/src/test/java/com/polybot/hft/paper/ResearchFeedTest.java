package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.polymarket.ws.ClobMarketWebSocketClient;
import java.net.http.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.springframework.test.util.ReflectionTestUtils;

class ResearchFeedTest {
  final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
  final Clock clock = Clock.fixed(Instant.parse("2026-10-16T19:45:00Z"), ZoneOffset.UTC);
  final String condition = "0x" + "1".repeat(64);

  @SuppressWarnings("unchecked")
  ResearchFeed feed(int firstStatus, List<ResearchFeed.Input> inputs, boolean expired)
      throws Exception {
    var http = mock(HttpClient.class);
    var ws = mock(ClobMarketWebSocketClient.class);
    var first = new AtomicBoolean(true);
    when(http.send(any(HttpRequest.class), any(HttpResponse.BodyHandler.class)))
        .thenAnswer(
            call -> {
              HttpRequest request = call.getArgument(0);
              String url = request.uri().toString();
              int status = 200;
              String body;
              if (url.endsWith("/time")) body = "" + clock.instant().getEpochSecond();
              else if (url.contains("gamma-api")) {
                var row = mapper.createObjectNode();
                row.put("active", true)
                    .put("closed", false)
                    .put("negRisk", false)
                    .put("version", "v1")
                    .put("conditionId", condition)
                    .put("endDate", clock.instant().plusSeconds(expired ? -1 : 900).toString())
                    .put("slug", request.uri().getQuery().substring(5))
                    .put("acceptingOrders", true)
                    .put("feesEnabled", false)
                    .put("clobTokenIds", "[\"1\",\"2\"]");
                body = mapper.createArrayNode().add(row).toString();
              } else if (url.contains("/book?")) {
                if (first.getAndSet(false)) status = firstStatus;
                String token = request.uri().getQuery().substring("token_id=".length());
                body =
                    mapper
                        .createObjectNode()
                        .put("market", condition)
                        .put("asset_id", token)
                        .put("neg_risk", false)
                        .put("tick_size", "0.01")
                        .put("min_order_size", "5")
                        .toString();
              } else if (url.contains("/clob-markets/"))
                body =
                    "{\"mts\":0.01,\"mos\":5,\"ao\":true,\"fd\":{\"r\":0,\"e\":1,\"to\":true},\"t\":[{\"t\":\"1\"},{\"t\":\"2\"}]}";
              else if (url.contains("/v2/resolutions?")) body = "{\"data\":[]}";
              else throw new AssertionError(url);
              HttpResponse<String> response = mock(HttpResponse.class);
              when(response.statusCode()).thenReturn(status);
              when(response.body()).thenReturn(body);
              when(response.headers())
                  .thenReturn(
                      HttpHeaders.of(Map.of("Retry-After", List.of("120")), (a, b) -> true));
              return response;
            });
    var feed =
        new ResearchFeed(
            http, mapper, clock, new PaperJournal(mapper, clock, "", "test", "abc"), ws);
    ReflectionTestUtils.setField(feed, "enabled", true);
    ReflectionTestUtils.setField(feed, "fifteen", true);
    ReflectionTestUtils.setField(feed, "hourly", false);
    feed.listen(inputs::add);
    return feed;
  }

  @Test
  void missingSingleBookDoesNotStarveLaterMarketsAndCarriesExactEndpoint() throws Exception {
    var inputs = new ArrayList<ResearchFeed.Input>();
    var feed = feed(404, inputs, false);
    feed.poll();
    assertThat(inputs.stream().filter(i -> i.kind().equals("MARKET_UNAVAILABLE"))).hasSize(1);
    assertThat(inputs.stream().filter(i -> i.kind().equals("META"))).hasSize(5);
    assertThat(inputs.stream().filter(i -> i.kind().equals("FEED_ERROR"))).isEmpty();
    var unavailable =
        inputs.stream()
            .filter(i -> i.kind().equals("MARKET_UNAVAILABLE"))
            .findFirst()
            .orElseThrow();
    assertThat(unavailable.data().path("url").asText()).contains("/book?token_id=1");
    assertThat(unavailable.data().path("condition").asText()).isEqualTo(condition);
  }

  @Test
  void rateLimitStillBacksOffGloballyAndNeverPublishesUsableMetadata() throws Exception {
    var inputs = new ArrayList<ResearchFeed.Input>();
    var feed = feed(429, inputs, false);
    feed.poll();
    assertThat(inputs).hasSize(1);
    assertThat(inputs.getFirst().kind()).isEqualTo("FEED_ERROR");
    assertThat(inputs.getFirst().data().path("retryAfter").asLong())
        .isEqualTo(clock.millis() + 120000);
    feed.poll();
    assertThat(inputs).hasSize(1);
  }

  @Test
  void expiredDiscoveryDoesNotRequestUnavailableTradableBooks() throws Exception {
    var inputs = new ArrayList<ResearchFeed.Input>();
    feed(404, inputs, true).poll();
    assertThat(inputs).isEmpty();
  }
}
