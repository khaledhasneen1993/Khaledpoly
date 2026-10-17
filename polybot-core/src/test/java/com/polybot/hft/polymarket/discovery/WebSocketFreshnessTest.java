package com.polybot.hft.polymarket.discovery;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.config.HftProperties;
import com.polybot.hft.events.*;
import com.polybot.hft.polymarket.ws.*;
import java.net.http.HttpClient;
import java.time.*;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class WebSocketFreshnessTest {
  static class MutableClock extends Clock {
    Instant now = Instant.now();

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

  ClobMarketWebSocketClient client(MutableClock clock) {
    return new ClobMarketWebSocketClient(
        new HftProperties(null, null, null, null, null),
        HttpClient.newHttpClient(),
        new ObjectMapper().findAndRegisterModules(),
        clock,
        new HftEventsProperties(false, null, null, null, null),
        new NoopHftEventPublisher());
  }

  String book(long timestamp, String bid) {
    return "{\"event_type\":\"book\",\"asset_id\":\"123\",\"timestamp\":\""
        + timestamp
        + "\",\"bids\":[{\"price\":\""
        + bid
        + "\",\"size\":\"10\"}],\"asks\":[{\"price\":\"0.6\",\"size\":\"10\"}]}";
  }

  /** Change only the token field, never a timestamp containing the same digits. */
  String withAsset(String message, String assetId) {
    return message.replace("\"asset_id\":\"123\"", "\"asset_id\":\"" + assetId + "\"");
  }

  @Test
  void assetReplacementCannotRewriteTimestampContainingTokenDigits() {
    long withRepeatedDigits = 1800000123456L;
    String renamed = withAsset(book(withRepeatedDigits, "0.4"), "456");
    assertThat(renamed).contains("\"timestamp\":\"" + withRepeatedDigits + "\"");
    assertThat(renamed).contains("\"asset_id\":\"456\"");
    assertThat(renamed).doesNotContain("\"asset_id\":\"123\"");
  }

  @Test
  void oneFrameDeliversBothBooksAfterCachesHaveCompletedAndLegacyListenersRemainSupported() {
    var clock = new MutableClock();
    var client = client(clock);
    var frames = new java.util.ArrayList<com.fasterxml.jackson.databind.JsonNode>();
    var legacy = new java.util.ArrayList<String>();
    client.onFrame(
        (k, n) -> {
          assertThat(k).isEqualTo("FRAME");
          assertThat(client.getTopOfBook("123")).isPresent();
          assertThat(client.getTopOfBook("456")).isPresent();
          frames.add(n);
        });
    client.onTape((k, n) -> legacy.add(k));
    ReflectionTestUtils.invokeMethod(
        client,
        "handleMessage",
        "["
            + book(clock.millis(), "0.5")
            + ","
            + withAsset(book(clock.millis(), "0.4"), "456")
            + "]");
    assertThat(frames).hasSize(1);
    assertThat(frames.getFirst().path("events")).hasSize(2);
    assertThat(legacy).containsExactly("BOOK", "BOOK");
  }

  @Test
  void ignoresOutOfOrderBookAndTradeDoesNotRefreshBookAge() {
    var clock = new MutableClock();
    var client = client(clock);
    long stamp = clock.millis();
    ReflectionTestUtils.invokeMethod(client, "handleMessage", book(stamp, "0.5"));
    Instant original = client.getTopOfBook("123").orElseThrow().updatedAt();
    ReflectionTestUtils.invokeMethod(client, "handleMessage", book(stamp - 500, "0.4"));
    assertThat(client.getTopOfBook("123").orElseThrow().bestBid()).isEqualByComparingTo("0.5");
    clock.now = clock.now.plusSeconds(1);
    ReflectionTestUtils.invokeMethod(
        client,
        "handleMessage",
        "{\"event_type\":\"last_trade_price\",\"asset_id\":\"123\",\"price\":\"0.55\"}");
    assertThat(client.getTopOfBook("123").orElseThrow().updatedAt()).isEqualTo(original);
  }

  @Test
  void staleSourceInvalidatesTradableBook() {
    var clock = new MutableClock();
    var client = client(clock);
    ReflectionTestUtils.invokeMethod(client, "handleMessage", book(clock.millis(), "0.5"));
    ReflectionTestUtils.invokeMethod(client, "handleMessage", book(clock.millis() - 10000, "0.4"));
    assertThat(client.getTopOfBook("123")).isEmpty();
  }

  @Test
  void slowRecorderDoesNotTurnStaleSourceIntoFreshDataAndExposesStageDelay() {
    var clock = new MutableClock();
    var client = client(clock);
    long at = clock.millis();
    var gaps = new java.util.ArrayList<com.fasterxml.jackson.databind.JsonNode>();
    client.onTape(
        (kind, data) -> {
          if (kind.equals("GAP")) gaps.add(data);
        });
    var recorder =
        new com.polybot.hft.paper.PaperJournal(new ObjectMapper(), clock, "", "test", "abc") {
          @Override
          public synchronized long record(String kind, Long sourceMs, Object data) {
            if (kind.equals("RAW_MARKET")) {
              assertThat(((java.util.Map<?, ?>) data).get("callbackReceivedMs")).isEqualTo(at);
              clock.now = clock.now.plusSeconds(3);
            }
            return clock.millis();
          }
        };
    ReflectionTestUtils.setField(client, "journal", recorder);
    ReflectionTestUtils.invokeMethod(client, "handleMessage", book(at, "0.5"));
    assertThat(client.getTopOfBook("123")).isEmpty();
    assertThat(gaps).hasSize(1);
    assertThat(gaps.getFirst().path("reason").asText()).isEqualTo("stale_source");
    assertThat(gaps.getFirst().path("callbackSourceAgeMs").asLong()).isZero();
    assertThat(gaps.getFirst().path("processingAgeMs").asLong()).isEqualTo(3000);
  }

  @Test
  void splitVenueUpdateStaysUntradableUntilFullSnapshotAndThenAvoidsRedundantReconnect() {
    var clock = new MutableClock();
    var client = client(clock);
    long at = clock.millis();
    ReflectionTestUtils.invokeMethod(client, "handleMessage", book(at, "0.5"));
    String cross =
        "{\"event_type\":\"price_change\",\"timestamp\":\""
            + at
            + "\",\"price_changes\":[{\"asset_id\":\"123\",\"side\":\"BUY\",\"price\":\"0.6\",\"size\":\"10\"}]}";
    ReflectionTestUtils.invokeMethod(client, "handleMessage", cross);
    assertThat(client.getTopOfBook("123")).isEmpty();
    assertThat((Boolean) ReflectionTestUtils.invokeMethod(client, "needsResnapshot")).isTrue();
    // The venue's second delta removes the crossed ask but cannot substitute for a full snapshot.
    ReflectionTestUtils.invokeMethod(
        client,
        "handleMessage",
        cross.replace("BUY", "SELL").replace("\"size\":\"10\"", "\"size\":\"0\""));
    assertThat(client.getTopOfBook("123")).isEmpty();
    assertThat((Boolean) ReflectionTestUtils.invokeMethod(client, "needsResnapshot")).isTrue();
    ReflectionTestUtils.invokeMethod(client, "handleMessage", book(at, "0.5"));
    assertThat(client.getTopOfBook("123")).isPresent();
    assertThat((Boolean) ReflectionTestUtils.invokeMethod(client, "needsResnapshot")).isFalse();
  }

  @Test
  void rawReplayMatchesStreamingInvalidationAndStaleTradePolicies() throws Exception {
    var clock = new MutableClock();
    clock.now = Instant.ofEpochMilli(1800000000000L);
    long at = clock.millis();
    var client = client(clock);
    var mapper = new ObjectMapper();
    var raw = new com.polybot.hft.paper.RawTapeNormalizer(mapper);
    var streamed = new java.util.ArrayList<com.fasterxml.jackson.databind.JsonNode>();
    client.onFrame((kind, frame) -> frame.path("events").forEach(streamed::add));
    String delta =
        "{\"event_type\":\"price_change\",\"timestamp\":\""
            + at
            + "\",\"price_changes\":[{\"asset_id\":\"123\",\"side\":\"BUY\",\"price\":\".5\",\"size\":\"9\"}]}";
    var frames =
        java.util.List.of(
            delta,
            book(at, ".5"),
            withAsset(book(at, ".4"), "456"),
            "{\"event_type\":\"last_trade_price\",\"asset_id\":\"123\",\"timestamp\":\""
                + (at - 90000)
                + "\",\"price\":\".5\",\"size\":\"5\",\"side\":\"SELL\"}",
            delta,
            book(at - 90000, ".5"),
            delta,
            withAsset(delta, "456"),
            book(at + 1, ".5"),
            book(at, ".5"),
            delta.replace(".5", ".6"),
            delta,
            book(at, ".5"),
            "[" + withAsset(book(at, ".4"), "789") + "," + book(at, ".7") + "]",
            withAsset(delta, "789"),
            "{invalid-json");
    for (String text : frames) {
      streamed.clear();
      var decoded = new java.util.ArrayList<com.fasterxml.jackson.databind.JsonNode>();
      raw.accept(
          text,
          at,
          (kind, data) -> {
            var event = mapper.createObjectNode().put("kind", kind);
            event.set("data", data);
            decoded.add(event);
          });
      ReflectionTestUtils.invokeMethod(client, "handleMessage", text);
      java.util.function.Function<
              java.util.List<com.fasterxml.jackson.databind.JsonNode>,
              com.fasterxml.jackson.databind.JsonNode>
          canonical =
              events -> {
                var result = mapper.createArrayNode();
                for (var event : events) {
                  var copy = event.deepCopy();
                  if (copy.path("kind").asText().equals("GAP")) {
                    var data = mapper.createObjectNode();
                    for (String key : java.util.List.of("reason", "token", "sourceMs"))
                      if (copy.path("data").has(key)) data.set(key, copy.path("data").path(key));
                    ((com.fasterxml.jackson.databind.node.ObjectNode) copy).set("data", data);
                  }
                  result.add(copy);
                }
                try {
                  return mapper.readTree(mapper.writeValueAsString(result));
                } catch (Exception e) {
                  throw new IllegalStateException(e);
                }
              };
      assertThat(canonical.apply(decoded))
          .as("raw/streaming contract for %s", text)
          .isEqualTo(canonical.apply(streamed));
    }
  }

  @Test
  void frameRecordsOneDecoderClockForBoundaryFreshnessReplay() throws Exception {
    var clock = new MutableClock();
    clock.now = Instant.ofEpochMilli(1800000000000L);
    long at = clock.millis();
    var advancingMapper =
        new ObjectMapper() {
          @Override
          public com.fasterxml.jackson.databind.JsonNode readTree(String text)
              throws com.fasterxml.jackson.core.JsonProcessingException {
            clock.now = clock.now.plusMillis(1);
            return super.readTree(text);
          }
        };
    var client =
        new ClobMarketWebSocketClient(
            new HftProperties(null, null, null, null, null),
            HttpClient.newHttpClient(),
            advancingMapper,
            clock,
            new HftEventsProperties(false, null, null, null, null),
            new NoopHftEventPublisher());
    var frames = new java.util.ArrayList<com.fasterxml.jackson.databind.JsonNode>();
    client.onFrame((kind, frame) -> frames.add(frame));
    String text = book(at + 1, ".5");
    ReflectionTestUtils.invokeMethod(client, "handleMessage", text);
    var frame = frames.getFirst();
    assertThat(clock.millis()).isEqualTo(at + 1);
    assertThat(frame.path("decodedMs").asLong()).isEqualTo(at);
    assertThat(frame.path("events").get(0).path("kind").asText()).isEqualTo("GAP");
    var replay = new com.polybot.hft.paper.RawTapeNormalizer(new ObjectMapper());
    var kinds = new java.util.ArrayList<String>();
    replay.accept(text, frame.path("decodedMs").asLong(), (kind, data) -> kinds.add(kind));
    assertThat(kinds).containsExactly("GAP");
  }
}
