package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.*;
import java.util.*;

/**
 * Markouts use the first fresh book observed AFTER each horizon; missing observations stay missing.
 */
public final class PaperMetrics {
  private record Pending(PaperMatchingEngine.Fill fill, int horizon) {}

  private final List<Pending> pending = new ArrayList<>();
  private final Map<Integer, BigDecimal> totals = new TreeMap<>();
  private final Map<Integer, Integer> counts = new TreeMap<>();
  private BigDecimal bought = BigDecimal.ZERO, sold = BigDecimal.ZERO;
  private int fills;

  public synchronized void fill(PaperMatchingEngine.Fill f) {
    fills++;
    if (f.buy()) bought = bought.add(f.size());
    else sold = sold.add(f.size());
    for (int h : new int[] {1000, 5000, 30000}) pending.add(new Pending(f, h));
  }

  public synchronized void book(JsonNode n, long at) {
    BigDecimal bid = null, ask = null;
    for (var r : n.path("bids")) {
      var p = PaperMatchingEngine.decimal(r, "price");
      bid = bid == null ? p : bid.max(p);
    }
    for (var r : n.path("asks")) {
      var p = PaperMatchingEngine.decimal(r, "price");
      ask = ask == null ? p : ask.min(p);
    }
    if (bid == null || ask == null) return;
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
      }
      if (at - due > 2000 || n.path("sourceMs").asLong() >= due) it.remove();
    }
  }

  public synchronized Map<String, Object> snapshot(long now) {
    pending.removeIf(p -> now > p.fill.at() + p.horizon + 2000);
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
        "incentives",
        BigDecimal.ZERO);
  }
}
