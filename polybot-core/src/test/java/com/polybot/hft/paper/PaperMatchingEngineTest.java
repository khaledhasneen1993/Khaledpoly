package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import org.junit.jupiter.api.*;

class PaperMatchingEngineTest {
  final ObjectMapper mapper = new ObjectMapper();
  PaperMatchingEngine engine = new PaperMatchingEngine(100, 100, 2000, new BigDecimal("2"));

  JsonNode n(String json) throws Exception {
    return mapper.readTree(json);
  }

  void book(long at, String size) throws Exception {
    engine.accept(
        "BOOK",
        at,
        n(
            "{\"token\":\"u\",\"sourceMs\":"
                + at
                + ",\"bids\":[{\"price\":\"0.3\",\"size\":\"100\"},{\"price\":\"0.4\",\"size\":\""
                + size
                + "\"}],\"asks\":[{\"price\":\"0.6\",\"size\":\"100\"}]}"));
  }

  void order(String id, String side, String price) throws Exception {
    engine.accept(
        "ORDER",
        1000,
        n(
            "{\"id\":\""
                + id
                + "\",\"token\":\"u\",\"side\":\""
                + side
                + "\",\"price\":\""
                + price
                + "\",\"size\":\"5\"}"));
  }

  PaperMatchingEngine.Update trade(long at, String id, String side, String price, String size)
      throws Exception {
    return engine.accept(
        "TRADE",
        at,
        n(
            "{\"token\":\"u\",\"tradeId\":\""
                + id
                + "\",\"side\":\""
                + side
                + "\",\"price\":\""
                + price
                + "\",\"size\":\""
                + size
                + "\",\"sourceMs\":"
                + at
                + "}"));
  }

  @Test
  void queuePartialAndDuplicatePrints() throws Exception {
    book(1000, "10");
    order("a", "BUY", "0.4");
    assertThat(trade(1050, "early", "SELL", "0.4", "100").fills()).isEmpty();
    assertThat(trade(1101, "first", "SELL", "0.4", "22").fills())
        .singleElement()
        .satisfies(f -> assertThat(f.size()).isEqualByComparingTo("2"));
    assertThat(trade(1102, "first", "SELL", "0.4", "22").fills()).isEmpty();
    var last = trade(1103, "last", "SELL", "0.4", "3");
    assertThat(last.fills())
        .singleElement()
        .satisfies(f -> assertThat(f.size()).isEqualByComparingTo("3"));
    assertThat(last.terminal()).containsEntry("a", "FILLED");
  }

  @Test
  void injectedLatencyActuallyDelaysActivationAndRetainsPrintRequirement() throws Exception {
    engine = new PaperMatchingEngine(100, 100, 2000, new BigDecimal("2"), 500, 42);
    long due = 1000 + new LatencyProfile(100, 500, 42).delay("activate", "a");
    book(1000, "0");
    order("a", "BUY", "0.4");
    assertThat(trade(due - 1, "early-jitter", "SELL", "0.4", "100").fills()).isEmpty();
    assertThat(engine.accept("TICK", due, n("{}")).fills()).isEmpty();
    assertThat(trade(due + 1, "after-jitter", "SELL", "0.4", "2").fills())
        .singleElement()
        .satisfies(f -> assertThat(f.size()).isEqualByComparingTo("2"));
  }

  @Test
  void touchesAndWrongSideNeverFill() throws Exception {
    book(1000, "0");
    order("a", "BUY", "0.4");
    assertThat(trade(1101, "buy", "BUY", "0.4", "500").fills()).isEmpty();
    assertThat(trade(1102, "other", "SELL", "0.41", "500").fills()).isEmpty();
    book(1103, "0");
    assertThat(engine.accept("TICK", 1104, n("{}")).fills()).isEmpty();
  }

  @Test
  void queueCancellationsReceiveNoCredit() throws Exception {
    book(1000, "10");
    order("a", "BUY", "0.4");
    engine.accept("TICK", 1100, n("{}"));
    book(1101, "0");
    assertThat(trade(1102, "x", "SELL", "0.4", "20").fills()).isEmpty();
    assertThat(trade(1103, "y", "SELL", "0.4", "1").fills()).hasSize(1);
  }

  @Test
  void cancellationRaceAndTie() throws Exception {
    book(1000, "0");
    order("a", "BUY", "0.4");
    engine.accept("CANCEL", 1100, n("{\"id\":\"a\"}"));
    assertThat(trade(1150, "race", "SELL", "0.4", "2").fills()).hasSize(1);
    var cancel = trade(1200, "tie", "SELL", "0.4", "20");
    assertThat(cancel.fills()).isEmpty();
    assertThat(cancel.terminal()).containsEntry("a", "CANCELED");
  }

  @Test
  void gapCancelsAndNeedsNewSnapshot() throws Exception {
    book(1000, "0");
    order("a", "BUY", "0.4");
    assertThat(engine.accept("GAP", 1100, n("{}")).terminal()).containsEntry("a", "CANCELED");
    assertThat(trade(1101, "late", "SELL", "0.4", "100").fills()).isEmpty();
    assertThat(engine.gaps()).isEqualTo(1);
  }

  @Test
  void activationUsesPastBookAndRejectsCrossing() throws Exception {
    book(1000, "0");
    order("a", "BUY", "0.65");
    assertThat(engine.accept("TICK", 1100, n("{}")).terminal()).containsEntry("a", "REJECTED");
  }

  @Test
  void staleAndOutOfOrderEventsCannotCreateFills() throws Exception {
    book(1000, "0");
    order("a", "BUY", "0.4");
    assertThat(trade(4000, "stale", "SELL", "0.4", "100").fills()).isEmpty();
    assertThatThrownBy(() -> engine.accept("TICK", 3000, n("{}")))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void sellOrdersUseBuyAggressors() throws Exception {
    book(1000, "0");
    order("a", "SELL", "0.6");
    assertThat(trade(1101, "wrong", "SELL", "0.6", "1000").fills()).isEmpty();
    assertThat(trade(1102, "right", "BUY", "0.6", "203").fills())
        .singleElement()
        .satisfies(f -> assertThat(f.size()).isEqualByComparingTo("3"));
  }

  @Test
  void multipleOwnOrdersCannotReuseVolume() throws Exception {
    book(1000, "0");
    order("a", "BUY", "0.4");
    order("b", "BUY", "0.4");
    var u = trade(1101, "one", "SELL", "0.4", "7");
    assertThat(u.fills()).hasSize(2);
    assertThat(
            u.fills().stream()
                .map(PaperMatchingEngine.Fill::size)
                .reduce(BigDecimal.ZERO, BigDecimal::add))
        .isEqualByComparingTo("7");
    assertThat(trade(1102, "two", "SELL", "0.4", "3").fills())
        .singleElement()
        .satisfies(f -> assertThat(f.size()).isEqualByComparingTo("3"));
  }

  @Test
  void sameTimestampDoesNotTradeBeforeActivation() throws Exception {
    book(1000, "0");
    order("a", "BUY", "0.4");
    assertThat(trade(1100, "tie", "SELL", "0.4", "100").fills()).isEmpty();
  }

  @Test
  void silentStalenessCancelsActiveQueueBeforeNewSnapshotCanReviveIt() throws Exception {
    book(1000, "10");
    order("a", "BUY", "0.4");
    engine.accept("TICK", 1100, n("{}"));
    assertThat(engine.accept("TICK", 3101, n("{}")).terminal()).containsEntry("a", "CANCELED");
    book(3102, "0");
    assertThat(trade(3103, "late", "SELL", "0.4", "500").fills()).isEmpty();
    assertThat(engine.gaps()).isEqualTo(1);
  }
}
