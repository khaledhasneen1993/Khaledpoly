package com.polybot.hft.polymarket.ws;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.util.*;

/** Full price-level book. A missing initial snapshot cannot be replaced by a top-price hint. */
public final class LocalOrderBook {
  private final NavigableMap<BigDecimal, BigDecimal> bids = new TreeMap<>(), asks = new TreeMap<>();

  public record Best(BigDecimal bid, BigDecimal ask, BigDecimal bidSize, BigDecimal askSize) {}

  public synchronized void snapshot(JsonNode buys, JsonNode sells) {
    if (!buys.isArray() || !sells.isArray())
      throw new IllegalArgumentException("Invalid book snapshot");
    var nextBids = new TreeMap<BigDecimal, BigDecimal>();
    var nextAsks = new TreeMap<BigDecimal, BigDecimal>();
    for (JsonNode level : buys)
      put(
          nextBids,
          new BigDecimal(level.path("price").asText()),
          new BigDecimal(level.path("size").asText()));
    for (JsonNode level : sells)
      put(
          nextAsks,
          new BigDecimal(level.path("price").asText()),
          new BigDecimal(level.path("size").asText()));
    bids.clear();
    bids.putAll(nextBids);
    asks.clear();
    asks.putAll(nextAsks);
    validate();
  }

  private static void put(
      NavigableMap<BigDecimal, BigDecimal> side, BigDecimal price, BigDecimal size) {
    if (price.signum() < 0 || price.compareTo(BigDecimal.ONE) > 0 || size.signum() < 0)
      throw new IllegalArgumentException("Invalid price level");
    if (size.signum() == 0) side.remove(price);
    else side.put(price, size);
  }

  public synchronized void change(String side, BigDecimal price, BigDecimal size) {
    if (!side.equals("BUY") && !side.equals("SELL"))
      throw new IllegalArgumentException("Invalid book side");
    put(side.equals("BUY") ? bids : asks, price, size);
    validate();
  }

  /**
   * Apply one venue batch atomically: intermediate levels may cross while the final book does not.
   */
  public synchronized void changes(JsonNode rows) {
    var nextBids = new TreeMap<>(bids);
    var nextAsks = new TreeMap<>(asks);
    if (!rows.isArray()) throw new IllegalArgumentException("Invalid depth batch");
    for (var row : rows) {
      String side = row.path("side").asText();
      if (!side.equals("BUY") && !side.equals("SELL"))
        throw new IllegalArgumentException("Invalid side");
      put(
          side.equals("BUY") ? nextBids : nextAsks,
          new BigDecimal(row.path("price").asText()),
          new BigDecimal(row.path("size").asText()));
    }
    if (!nextBids.isEmpty()
        && !nextAsks.isEmpty()
        && nextBids.lastKey().compareTo(nextAsks.firstKey()) >= 0)
      throw new IllegalStateException("Crossed final batch");
    bids.clear();
    bids.putAll(nextBids);
    asks.clear();
    asks.putAll(nextAsks);
  }

  private void validate() {
    if (!bids.isEmpty() && !asks.isEmpty() && bids.lastKey().compareTo(asks.firstKey()) >= 0)
      throw new IllegalStateException("Crossed book; require resnapshot");
  }

  public synchronized Map<String, Object> depth() {
    return Map.of(
        "bids",
        bids.entrySet().stream()
            .map(
                e ->
                    Map.of(
                        "price", e.getKey().toPlainString(), "size", e.getValue().toPlainString()))
            .toList(),
        "asks",
        asks.entrySet().stream()
            .map(
                e ->
                    Map.of(
                        "price", e.getKey().toPlainString(), "size", e.getValue().toPlainString()))
            .toList());
  }

  public synchronized Best best() {
    return new Best(
        bids.isEmpty() ? null : bids.lastKey(),
        asks.isEmpty() ? null : asks.firstKey(),
        bids.isEmpty() ? null : bids.lastEntry().getValue(),
        asks.isEmpty() ? null : asks.firstEntry().getValue());
  }
}
