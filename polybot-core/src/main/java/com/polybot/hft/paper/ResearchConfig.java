package com.polybot.hft.paper;

import java.math.BigDecimal;

/** Frozen experiment parameters; serialize these before the first observation. */
public record ResearchConfig(
    int schema,
    BigDecimal initialCash,
    BigDecimal orderShares,
    BigDecimal minimumEdge,
    BigDecimal portfolioBudget,
    long activationMs,
    long cancelMs,
    long maxBookAgeMs,
    BigDecimal queueMultiplier,
    BigDecimal mergeCost,
    BigDecimal redemptionCost,
    long unhedgedMs,
    BigDecimal maxUnhedged,
    BigDecimal maxExitLoss,
    BigDecimal feeMultiplier,
    long decisionMillis,
    long metadataMaxAgeMs,
    long latencyJitterMs,
    long latencySeed) {
  public ResearchConfig(
      int schema,
      BigDecimal initialCash,
      BigDecimal orderShares,
      BigDecimal minimumEdge,
      BigDecimal portfolioBudget,
      long activationMs,
      long cancelMs,
      long maxBookAgeMs,
      BigDecimal queueMultiplier,
      BigDecimal mergeCost,
      BigDecimal redemptionCost,
      long unhedgedMs,
      BigDecimal maxUnhedged,
      BigDecimal maxExitLoss,
      BigDecimal feeMultiplier,
      long decisionMillis,
      long metadataMaxAgeMs) {
    this(
        schema,
        initialCash,
        orderShares,
        minimumEdge,
        portfolioBudget,
        activationMs,
        cancelMs,
        maxBookAgeMs,
        queueMultiplier,
        mergeCost,
        redemptionCost,
        unhedgedMs,
        maxUnhedged,
        maxExitLoss,
        feeMultiplier,
        decisionMillis,
        metadataMaxAgeMs,
        0,
        0);
  }

  public ResearchConfig {
    if (latencyJitterMs < 0
        || latencyJitterMs > 60000
        || schema != 1
        || initialCash.signum() <= 0
        || orderShares.signum() <= 0
        || minimumEdge.signum() < 0
        || portfolioBudget.signum() <= 0
        || activationMs < 0
        || cancelMs < 0
        || maxBookAgeMs <= 0
        || queueMultiplier.compareTo(BigDecimal.ONE) < 0
        || mergeCost.signum() < 0
        || redemptionCost.signum() < 0
        || unhedgedMs <= 0
        || maxUnhedged.signum() <= 0
        || maxExitLoss.signum() < 0
        || feeMultiplier.compareTo(BigDecimal.ONE) < 0
        || decisionMillis < 50
        || metadataMaxAgeMs <= 0)
      throw new IllegalArgumentException("Invalid research configuration");
  }

  public static ResearchConfig defaults() {
    return new ResearchConfig(
        1, b("500"), b("5"), b("0.01"), b("100"), 250, 250, 2000, b("2"), b("0.01"), b("0.01"),
        30000, b("25"), b("2.5"), b("1"), 250, 60000);
  }

  public ResearchConfig stress() {
    return new ResearchConfig(
        schema,
        initialCash,
        orderShares,
        minimumEdge,
        portfolioBudget,
        1000,
        1000,
        maxBookAgeMs,
        b("4"),
        mergeCost.add(b("0.05")),
        redemptionCost.add(b("0.05")),
        unhedgedMs,
        maxUnhedged,
        maxExitLoss,
        b("2"),
        decisionMillis,
        metadataMaxAgeMs,
        Math.max(latencyJitterMs, 500),
        latencySeed);
  }

  private static BigDecimal b(String s) {
    return new BigDecimal(s);
  }
}
