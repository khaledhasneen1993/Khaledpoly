package com.polybot.hft.paper;

import java.math.*;

/** Fee schedule inputs must come from the market snapshot, never from category guesses. */
public record FeeModel(BigDecimal rate, int exponent) {
  public FeeModel {
    if (rate == null || rate.signum() < 0 || exponent < 0 || exponent > 8)
      throw new IllegalArgumentException("Unknown fee schedule");
  }

  public BigDecimal fee(BigDecimal shares, BigDecimal price, boolean maker) {
    if (shares.signum() < 0 || price.signum() <= 0 || price.compareTo(BigDecimal.ONE) >= 0)
      throw new IllegalArgumentException("Invalid fee input");
    if (maker) return BigDecimal.ZERO;
    return shares
        .multiply(rate)
        .multiply(price.multiply(BigDecimal.ONE.subtract(price)).pow(exponent))
        .setScale(5, RoundingMode.HALF_UP);
  }
}
