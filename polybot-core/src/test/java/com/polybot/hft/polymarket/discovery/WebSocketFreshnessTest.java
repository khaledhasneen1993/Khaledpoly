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
}
