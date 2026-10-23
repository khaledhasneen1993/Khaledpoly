package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.*;
import java.util.*;

/**
 * Markouts use the first fresh book observed AFTER each horizon; missing observations stay missing.
 */
public final class PaperMetrics {
  private final java.util.function.Consumer<Map<String, Object>> observation;

  public PaperMetrics() {
    this(row -> {});
  }

  public PaperMetrics(java.util.function.Consumer<Map<String, Object>> observation) {
    this.observation = observation;
  }

  private record Pending(PaperMatchingEngine.Fill fill, int horizon, int fillSequence) {}

  private final List<Pending> pending = new ArrayList<>();
  private final Map<Integer, BigDecimal> totals = new TreeMap<>();
  private final Map<Integer, Integer> counts = new TreeMap<>();
  private final Map<String, Map<Integer, Integer>> missing = new TreeMap<>();
  private final Map<String, Long> bookSources = new HashMap<>();
  private BigDecimal bought = BigDecimal.ZERO, sold = BigDecimal.ZERO;
  private int fills;

  public synchronized void fill(PaperMatchingEngine.Fill f) {
    fills++;
    if (f.buy()) bought = bought.add(f.size());
    else sold = sold.add(f.size());
    for (int h : new int[] {1000, 5000, 30000}) pending.add(new Pending(f, h, fills));
  }

  public synchronized void book(JsonNode n, long at) {
    String token = n.path("token").asText();
    long source = n.path("sourceMs").asLong(-1);
    Long prior = bookSources.get(token);
    if (source < 0 || source > at || prior != null && source < prior) {
      invalidate(Set.of(token), "INVALID_BOOK");
      bookSources.remove(token);
      return;
    }
    BigDecimal bid = null, ask = null;
    for (var r : n.path("bids")) {
      var p = PaperMatchingEngine.decimal(r, "price");
      bid = bid == null ? p : bid.max(p);
    }
    for (var r : n.path("asks")) {
      var p = PaperMatchingEngine.decimal(r, "price");
      ask = ask == null ? p : ask.min(p);
    }
    if (bid == null || ask == null || bid.compareTo(ask) > 0) {
      invalidate(Set.of(token), "INVALID_BOOK");
      bookSources.remove(token);
      return;
    }
    bookSources.put(token, source);
    BigDecimal mid = bid.add(ask).divide(BigDecimal.valueOf(2));
    var it = pending.iterator();
    while (it.hasNext()) {
      var p = it.next();
      if (!p.fill.token().equals(n.path("token").asText())) continue;
      long due = p.fill.at() + p.horizon;
      if (at < due) continue;
      // Do not silently substitute a book minutes later for a 1s markout.
      if (at - due <= 2000 && n.path("sourceMs").asLong() >= due) {
        var edge =
            mid.subtract(p.fill.price())
                .multiply(p.fill.buy() ? BigDecimal.ONE : BigDecimal.ONE.negate());
        totals.merge(p.horizon, edge.multiply(p.fill.size()), BigDecimal::add);
        counts.merge(p.horizon, 1, Integer::sum);
        observation.accept(
            Map.of(
                "id",
                p.fill.id(),
                "fillSequence",
                p.fillSequence(),
                "token",
                p.fill.token(),
                "fillAt",
                p.fill.at(),
                "horizonMs",
                p.horizon,
                "observedMs",
                at,
                "sourceMs",
                n.path("sourceMs").asLong(),
                "perShare",
                edge,
                "quantity",
                p.fill.size()));
      }
      if (at - due > 2000) recordMissing(p, "OBSERVATION_WINDOW_EXPIRED");
      if (at - due > 2000 || n.path("sourceMs").asLong() >= due) it.remove();
    }
  }

  public synchronized void book(JsonNode n, long at, long maxBookAgeMs) {
    advance(at, maxBookAgeMs);
    long source = n.path("sourceMs").asLong(-1);
    if (source >= 0 && source <= at && at - source > maxBookAgeMs) {
      invalidate(Set.of(n.path("token").asText()), "STALE_DEPTH");
      bookSources.remove(n.path("token").asText());
      return;
    }
    book(n, at);
  }

  /** A recovered snapshot cannot repair uncertainty between a fill and its horizon. */
  public synchronized void gap(Set<String> tokens) {
    invalidate(tokens, "DATA_GAP");
    if (tokens.isEmpty()) bookSources.clear();
    else bookSources.keySet().removeAll(tokens);
  }

  /** Call before processing each arrival, including ticks and replacement snapshots. */
  public synchronized void advance(long at, long maxBookAgeMs) {
    var stale = new HashSet<String>();
    bookSources.forEach((token, source) -> {
      if (at - source > maxBookAgeMs) stale.add(token);
    });
    if (!stale.isEmpty()) {
      invalidate(stale, "STALE_DEPTH");
      bookSources.keySet().removeAll(stale);
    }
    expire(at);
  }

  private void invalidate(Set<String> tokens, String reason) {
    pending.removeIf(p -> {
      if (!tokens.isEmpty() && !tokens.contains(p.fill.token())) return false;
      recordMissing(p, reason);
      return true;
    });
  }

  private void recordMissing(Pending p, String reason) {
    missing.computeIfAbsent(reason, ignored -> new TreeMap<>())
        .merge(p.horizon, 1, Integer::sum);
  }

  private void expire(long now) {
    pending.removeIf(p -> {
      if (now <= p.fill.at() + p.horizon + 2000) return false;
      recordMissing(p, "OBSERVATION_WINDOW_EXPIRED");
      return true;
    });
  }

  public synchronized Map<String, Object> snapshot(long now) {
    expire(now);
    var missingSnapshot = new TreeMap<String, Map<Integer, Integer>>();
    missing.forEach((reason, horizons) -> missingSnapshot.put(reason, Map.copyOf(horizons)));
    return Map.of(
        "fills",
        fills,
        "boughtShares",
        bought,
        "soldShares",
        sold,
        "markoutPnl",
        Map.copyOf(totals),
        "markoutSamples",
        Map.copyOf(counts),
        "pendingMarkouts",
        pending.size(),
        "missingMarkoutsByReason",
        Map.copyOf(missingSnapshot),
        "markoutContinuityPolicy",
        "NO_GAP_OR_STALE_DEPTH_BETWEEN_FILL_AND_OBSERVATION",
        "incentives",
        BigDecimal.ZERO);
  }
}
