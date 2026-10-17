package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.polybot.hft.polymarket.ws.ClobMarketWebSocketClient;
import java.net.http.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class BroaderDiscoveryTest {
  final ObjectMapper mapper = new ObjectMapper();
  final Clock clock = Clock.fixed(Instant.parse("2026-10-17T09:00:00Z"), ZoneOffset.UTC);

  String condition(int i) {
    return "0x" + String.valueOf(i).repeat(64);
  }

  ObjectNode event() {
    var event = mapper.createObjectNode();
    event.put("id", "123").put("negRisk", true).put("closed", false).put("negRiskAugmented", false);
    var markets = mapper.createArrayNode();
    for (int i = 1; i <= 2; i++) {
      var row = mapper.createObjectNode();
      row.put("active", true)
          .put("closed", false)
          .put("negRisk", true)
          .put("version", "v1")
          .put("conditionId", condition(i))
          .put("startDate", clock.instant().minusSeconds(3600).toString())
          .put("endDate", clock.instant().plusSeconds(86400).toString())
          .put("slug", "candidate-" + i)
          .put("acceptingOrders", true)
          .put("clobTokenIds", "[\"" + (i * 2 - 1) + "\",\"" + (i * 2) + "\"]");
      row.set("outcomes", mapper.valueToTree(List.of("Yes", "No")));
      markets.add(row);
    }
    event.set("markets", markets);
    return event;
  }

  @SuppressWarnings("unchecked")
  List<ResearchFeed.Input> collect(boolean clobRisk) throws Exception {
    var http = mock(HttpClient.class);
    var ws = mock(ClobMarketWebSocketClient.class);
    when(http.send(any(HttpRequest.class), any(HttpResponse.BodyHandler.class)))
        .thenAnswer(
            call -> {
              var request = (HttpRequest) call.getArgument(0);
              String url = request.uri().toString(), body;
              if (url.endsWith("/time")) body = "" + clock.instant().getEpochSecond();
              else if (url.contains("/tags/slug/")) body = "{\"id\":\"1\",\"slug\":\"politics\"}";
              else if (url.contains("/events/keyset")) body = "{\"events\":[{\"id\":\"123\"}]}";
              else if (url.endsWith("/events/123")) body = event().toString();
              else if (url.contains("/book?")) {
                int token = Integer.parseInt(request.uri().getQuery().split("=")[1]);
                int member = (token + 1) / 2;
                body =
                    mapper
                        .createObjectNode()
                        .put("market", condition(member))
                        .put("asset_id", "" + token)
                        .put("neg_risk", true)
                        .put("tick_size", ".01")
                        .put("min_order_size", "5")
                        .toString();
              } else if (url.contains("/clob-markets/")) {
                int member = url.endsWith(condition(1)) ? 1 : 2;
                var n = mapper.createObjectNode();
                n.put("c", condition(member))
                    .put("mts", ".01")
                    .put("mos", "5")
                    .put("nr", clobRisk)
                    .put("ao", true);
                n.set("fd", mapper.valueToTree(Map.of("r", ".07", "e", 1, "to", true)));
                n.set(
                    "t",
                    mapper.valueToTree(
                        List.of(
                            Map.of("t", "" + (member * 2 - 1)), Map.of("t", "" + (member * 2)))));
                body = n.toString();
              } else if (url.contains("/v2/resolutions?")) body = "{\"data\":[]}";
              else throw new AssertionError(url);
              var response = (HttpResponse<String>) mock(HttpResponse.class);
              when(response.statusCode()).thenReturn(200);
              when(response.body()).thenReturn(body);
              return response;
            });
    var inputs = new ArrayList<ResearchFeed.Input>();
    try (var journal = new PaperJournal(mapper, clock, "", "test", "test")) {
      var feed = new ResearchFeed(http, mapper, clock, journal, ws);
      for (var entry :
          Map.of(
                  "enabled",
                  true,
                  "externalPaper",
                  true,
                  "five",
                  false,
                  "fifteen",
                  false,
                  "hourly",
                  false)
              .entrySet()) ReflectionTestUtils.setField(feed, entry.getKey(), entry.getValue());
      ReflectionTestUtils.setField(feed, "broaderTags", "politics");
      feed.listen(inputs::add);
      feed.poll();
      if (clobRisk) verify(ws).setSubscribedAssets(List.of("1", "2", "3", "4"));
      else verify(ws, never()).setSubscribedAssets(any());
    }
    return inputs;
  }

  @Test
  void categoryDetailDiscoveryPreservesStartAndValidatesNegativeRisk() throws Exception {
    var inputs = collect(true);
    assertThat(inputs.stream().filter(i -> i.kind().equals("META"))).hasSize(2);
    for (var input : inputs)
      if (input.kind().equals("META")) {
        assertThat(input.data().path("negativeRisk").asBoolean()).isTrue();
        assertThat(input.data().path("startMs").asLong()).isEqualTo(clock.millis() - 3600000);
        assertThat(input.data().path("feeRate").decimalValue()).isEqualByComparingTo(".07");
      }
    assertThat(inputs.stream().filter(i -> i.kind().equals("FEED_ERROR"))).isEmpty();
  }

  @Test
  void mismatchedRiskDoesNotPublishTradableMetadata() throws Exception {
    var inputs = collect(false);
    assertThat(inputs.stream().filter(i -> i.kind().equals("META"))).isEmpty();
    assertThat(inputs.stream().filter(i -> i.kind().equals("MARKET_UNAVAILABLE"))).hasSize(2);
  }
}
