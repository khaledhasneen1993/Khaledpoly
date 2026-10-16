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
}
