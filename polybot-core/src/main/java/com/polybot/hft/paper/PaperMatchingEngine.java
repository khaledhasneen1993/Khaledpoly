package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.util.*;

/**
 * Deterministic, deliberately conservative L2 maker model shared by streaming PAPER and replay. No
 * cancellation credit, no touch fills, no inferred trades, no fills across data gaps. Public prints
 * do not reveal exact queue position: this is a model, never execution evidence.
 */
public final class PaperMatchingEngine {
  public record Fill(
      String id, String token, boolean buy, BigDecimal price, BigDecimal size, long at) {}

  public record Update(List<Fill> fills, Map<String, String> terminal) {}

  private record Book(
      NavigableMap<BigDecimal, BigDecimal> bids,
      NavigableMap<BigDecimal, BigDecimal> asks,
      long source) {}

  private static final class Order {
    String id, token;
    boolean buy, active;
    BigDecimal price, remaining, ahead;
    long activation, cancel = Long.MAX_VALUE;
  }

  private final Map<String, Book> books = new HashMap<>();
  private final LinkedHashMap<String, Order> orders = new LinkedHashMap<>();
  private final Set<String> tradeIds = new HashSet<>(), orderIds = new HashSet<>();
  private final long latency, cancelLatency, maxAge;
  private final BigDecimal queueMultiplier;
  private long now = -1;
  private int gaps, duplicates;

  public PaperMatchingEngine(
      long latency, long cancelLatency, long maxAge, BigDecimal queueMultiplier) {
    if (latency < 0
        || cancelLatency < 0
        || maxAge <= 0
        || queueMultiplier.compareTo(BigDecimal.ONE) < 0)
      throw new IllegalArgumentException("Invalid matching assumptions");
    this.latency = latency;
    this.cancelLatency = cancelLatency;
    this.maxAge = maxAge;
    this.queueMultiplier = queueMultiplier;
  }

  public int gaps() {
    return gaps;
  }

  public int duplicates() {
    return duplicates;
  }

  public synchronized Update accept(String kind, long at, JsonNode n) {
    if (at < now) throw new IllegalArgumentException("Arrival clock moved backwards");
    now = at;
    var fills = new ArrayList<Fill>();
    var terminal = new LinkedHashMap<String, String>();
    if (kind.equals("GAP")) {
      invalidate(terminal);
      orders.clear();
      return new Update(List.of(), Map.copyOf(terminal));
    }
    var staleTokens = new HashSet<String>();
    for (var o : orders.values())
      if (o.active) {
        Book b = books.get(o.token);
        if (b == null || at - b.source > maxAge) staleTokens.add(o.token);
      }
    for (String token : staleTokens) {
      books.remove(token);
      gaps++;
    }
    orders.values().stream()
        .filter(o -> staleTokens.contains(o.token))
        .forEach(o -> terminal.put(o.id, "CANCELED"));
    terminal.keySet().forEach(orders::remove);
    // Due cancels win ties. Activation uses only the book known BEFORE this event.
    for (var o : orders.values()) {
      if (o.cancel <= at) {
        terminal.put(o.id, "CANCELED");
        continue;
      }
      if (!o.active && o.activation <= at) {
        Book b = books.get(o.token);
        if (b == null || at - b.source > maxAge || b.bids.isEmpty() || b.asks.isEmpty()) {
          terminal.put(o.id, "REJECTED");
          continue;
        }
        if (o.buy
            ? o.price.compareTo(b.asks.firstKey()) >= 0
            : o.price.compareTo(b.bids.lastKey()) <= 0) {
          terminal.put(o.id, "REJECTED");
          continue;
        }
        o.ahead =
            (o.buy ? b.bids : b.asks)
                .getOrDefault(o.price, BigDecimal.ZERO)
                .multiply(queueMultiplier);
        for (var prior : orders.values()) {
          if (prior == o) break;
          if (!terminal.containsKey(prior.id)
              && prior.active
              && prior.token.equals(o.token)
              && prior.buy == o.buy
              && prior.price.compareTo(o.price) == 0) o.ahead = o.ahead.add(prior.remaining);
        }
        o.active = true;
      }
    }
    terminal.keySet().forEach(orders::remove);
    switch (kind) {
      case "BOOK" -> {
        String token = required(n, "token");
        long source = n.path("sourceMs").asLong(-1);
        if (source < 0
            || source > at
            || at - source > maxAge
            || (books.containsKey(token) && source < books.get(token).source)) {
          invalidate(terminal);
          break;
        }
        var bids = levels(n.path("bids"));
        var asks = levels(n.path("asks"));
        if (!bids.isEmpty() && !asks.isEmpty() && bids.lastKey().compareTo(asks.firstKey()) >= 0)
          throw new IllegalArgumentException("Crossed recorded book");
        books.put(token, new Book(bids, asks, source));
      }
      case "ORDER" -> {
        Order o = new Order();
        o.id = required(n, "id");
        o.token = required(n, "token");
        String side = required(n, "side");
        if (!side.equals("BUY") && !side.equals("SELL"))
          throw new IllegalArgumentException("Invalid side");
        o.buy = side.equals("BUY");
        o.price = decimal(n, "price");
        o.remaining = decimal(n, "size");
        if (o.price.signum() <= 0
            || o.price.compareTo(BigDecimal.ONE) >= 0
            || o.remaining.signum() <= 0
            || !orderIds.add(o.id))
          throw new IllegalArgumentException("Invalid or duplicate order");
        o.activation = Math.addExact(at, latency);
        orders.put(o.id, o);
      }
      case "CANCEL" -> {
        Order o = orders.get(required(n, "id"));
        if (o != null) o.cancel = Math.min(o.cancel, Math.addExact(at, cancelLatency));
      }
      case "TRADE" -> {
        String token = required(n, "token"),
            id = required(n, "tradeId"),
            side = required(n, "side");
        if (!side.equals("BUY") && !side.equals("SELL"))
          throw new IllegalArgumentException("Unknown aggressor side");
        BigDecimal price = decimal(n, "price"), volume = decimal(n, "size");
        if (volume.signum() <= 0 || price.signum() <= 0 || price.compareTo(BigDecimal.ONE) >= 0)
          throw new IllegalArgumentException("Invalid trade");
        if (tradeIds.size() >= 1_000_000)
          throw new IllegalStateException("Rotate tape at one million trades");
        if (!tradeIds.add(id)) {
          duplicates++;
          break;
        }
        long source = n.path("sourceMs").asLong(-1);
        Book b = books.get(token);
        if (source < 0
            || source > at
            || at - source > maxAge
            || b == null
            || at - b.source > maxAge
            || source < b.source) break;
        for (var o : orders.values()) {
          if (!o.active
              || !o.token.equals(token)
              || o.buy == side.equals("BUY")
              || o.price.compareTo(price) != 0
              || source <= o.activation) continue;
          BigDecimal executable = volume.subtract(o.ahead).max(BigDecimal.ZERO).min(o.remaining);
          o.ahead = o.ahead.subtract(volume).max(BigDecimal.ZERO);
          if (executable.signum() > 0) {
            o.remaining = o.remaining.subtract(executable);
            fills.add(new Fill(o.id, o.token, o.buy, o.price, executable, at));
            if (o.remaining.signum() == 0) terminal.put(o.id, "FILLED");
          }
        }
      }
      case "CLOSE" -> {
        String token = required(n, "token");
        books.remove(token);
        orders.values().stream()
            .filter(o -> o.token.equals(token))
            .forEach(o -> terminal.put(o.id, "CANCELED"));
      }
      case "GAP" -> invalidate(terminal);
      case "TICK" -> {}
      default -> throw new IllegalArgumentException("Unknown matching event: " + kind);
    }
    terminal.keySet().forEach(orders::remove);
    return new Update(List.copyOf(fills), Map.copyOf(terminal));
  }

  private void invalidate(Map<String, String> terminal) {
    gaps++;
    books.clear();
    orders.keySet().forEach(id -> terminal.put(id, "CANCELED"));
  }

  private static NavigableMap<BigDecimal, BigDecimal> levels(JsonNode n) {
    if (!n.isArray()) throw new IllegalArgumentException("Depth array required");
    var result = new TreeMap<BigDecimal, BigDecimal>();
    for (var row : n) {
      BigDecimal p = decimal(row, "price"), s = decimal(row, "size");
      if (p.signum() <= 0 || p.compareTo(BigDecimal.ONE) >= 0 || s.signum() < 0)
        throw new IllegalArgumentException("Invalid depth");
      if (s.signum() > 0) result.put(p, s);
    }
    return result;
  }

  public static String required(JsonNode n, String k) {
    if (!n.hasNonNull(k) || n.path(k).asText().isBlank())
      throw new IllegalArgumentException("Missing " + k);
    return n.path(k).asText();
  }

  public static BigDecimal decimal(JsonNode n, String k) {
    return new BigDecimal(required(n, k));
  }
}
