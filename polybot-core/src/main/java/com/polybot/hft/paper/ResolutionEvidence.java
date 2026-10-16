package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.*;
import java.time.Instant;
import java.util.*;

/** Validate the official condition-grain terminal state, not a guessed winner or market price. */
public record ResolutionEvidence(
    String condition,
    Map<String, BigDecimal> payouts,
    String transaction,
    long resolvedMs,
    long observedMs,
    String source,
    JsonNode raw) {
  public static final String SOURCE = "https://data-api.polymarket.com/v2/resolutions";

  public static ResolutionEvidence parse(ResearchMarket market, JsonNode row, long observedMs) {
    if (!row.path("condition_id").asText().equals(market.condition())
        || !row.path("status").asText().equals("resolved")
        || !row.path("transaction_hash").asText().matches("0x[0-9a-fA-F]{64}")
        || row.path("resolved_block").asLong(0) <= 0
        || row.path("payouts").size() != 2)
      throw new IllegalArgumentException("Resolution is not verified terminal binary evidence");
    long resolved = Instant.parse(row.path("resolved_at").asText()).toEpochMilli();
    if (resolved > observedMs || resolved < market.startMs())
      throw new IllegalArgumentException("Future/invalid resolution");
    BigDecimal a = new BigDecimal(row.path("payouts").get(0).asText()),
        b = new BigDecimal(row.path("payouts").get(1).asText());
    if (a.signum() < 0 || b.signum() < 0 || a.add(b).signum() <= 0)
      throw new IllegalArgumentException("Invalid payout vector");
    BigDecimal sum = a.add(b);
    a = a.divide(sum, 18, RoundingMode.HALF_EVEN);
    b = BigDecimal.ONE.subtract(a);
    return new ResolutionEvidence(
        market.condition(),
        Map.of(market.first(), a, market.second(), b),
        row.path("transaction_hash").asText(),
        resolved,
        observedMs,
        SOURCE,
        row.deepCopy());
  }
}
