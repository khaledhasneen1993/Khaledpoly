package com.polybot.hft.paper;

import java.math.BigDecimal;

/** Token order is the venue outcome-slot order, never guessed from a display label. */
public record ResearchMarket(
    String condition,
    String first,
    String second,
    long startMs,
    long endMs,
    BigDecimal tick,
    BigDecimal minSize,
    BigDecimal feeRate,
    int feeExponent,
    boolean accepting,
    long observedMs,
    String evidence,
    boolean negativeRisk) {
  public ResearchMarket(
      String condition,
      String first,
      String second,
      long startMs,
      long endMs,
      BigDecimal tick,
      BigDecimal minSize,
      BigDecimal feeRate,
      int feeExponent,
      boolean accepting,
      long observedMs,
      String evidence) {
    this(
        condition,
        first,
        second,
        startMs,
        endMs,
        tick,
        minSize,
        feeRate,
        feeExponent,
        accepting,
        observedMs,
        evidence,
        false);
  }

  public ResearchMarket {
    if (condition == null
        || !condition.matches("0x[0-9a-fA-F]{64}")
        || first == null
        || second == null
        || first.equals(second)
        || startMs >= endMs
        || tick == null
        || tick.signum() <= 0
        || minSize == null
        || minSize.signum() <= 0
        || observedMs < 0
        || evidence == null
        || evidence.isBlank()) throw new IllegalArgumentException("Unverified binary metadata");
    new FeeModel(feeRate, feeExponent);
  }
}
