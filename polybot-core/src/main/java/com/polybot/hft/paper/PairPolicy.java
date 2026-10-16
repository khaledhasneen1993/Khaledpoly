package com.polybot.hft.paper;

import java.math.*;

/** Transparent risk premiums, not a fitted alpha model. All inputs must be causal observations. */
public final class PairPolicy {
  private PairPolicy() {}

  public static BigDecimal requiredEdge(
      BigDecimal base,
      BigDecimal volatility,
      long secondsToExpiry,
      BigDecimal depth,
      long latencyMs,
      BigDecimal imbalance) {
    if (base.signum() < 0 || volatility.signum() < 0 || depth.signum() <= 0 || latencyMs < 0)
      throw new IllegalArgumentException("Invalid edge inputs");
    BigDecimal latency = volatility.multiply(BigDecimal.valueOf(Math.sqrt(latencyMs / 1000.0)));
    BigDecimal expiry =
        secondsToExpiry < 60
            ? new BigDecimal("0.02")
            : secondsToExpiry < 180 ? new BigDecimal("0.01") : BigDecimal.ZERO;
    BigDecimal thin =
        BigDecimal.ONE
            .divide(depth.max(BigDecimal.ONE), 8, RoundingMode.UP)
            .min(new BigDecimal("0.02"));
    BigDecimal inventory =
        imbalance.abs().multiply(new BigDecimal("0.0005")).min(new BigDecimal("0.02"));
    return base.add(latency).add(expiry).add(thin).add(inventory);
  }

  public record HedgeChoice(String action, BigDecimal completeValue, BigDecimal sellValue) {}

  public static HedgeChoice hedge(
      BigDecimal leadBasis,
      BigDecimal oppositeAsk,
      BigDecimal leadBid,
      BigDecimal buyFeePerShare,
      BigDecimal sellFeePerShare,
      BigDecimal minimumEdge,
      boolean overdue) {
    BigDecimal complete =
        BigDecimal.ONE.subtract(leadBasis).subtract(oppositeAsk).subtract(buyFeePerShare);
    BigDecimal sell = leadBid.subtract(leadBasis).subtract(sellFeePerShare);
    if (complete.compareTo(minimumEdge) >= 0 && complete.compareTo(sell) >= 0)
      return new HedgeChoice("COMPLETE", complete, sell);
    if (overdue)
      return new HedgeChoice(
          complete.compareTo(sell) >= 0 ? "RISK_COMPLETE" : "RISK_SELL", complete, sell);
    return new HedgeChoice("WAIT", complete, sell);
  }
}
