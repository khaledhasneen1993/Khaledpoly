package com.polybot.hft.paper;

import java.math.*;
import java.util.*;

/**
 * Offline taker evaluation only. Never enables live broadcast or consumes imaginary top-level
 * depth.
 */
public final class DepthExecution {
  public record Result(BigDecimal size, BigDecimal notional, BigDecimal fee, BigDecimal average) {}

  public static Result sweep(
      NavigableMap<BigDecimal, BigDecimal> levels,
      boolean buy,
      BigDecimal quantity,
      BigDecimal limit,
      FeeModel fees) {
    if (quantity.signum() <= 0) throw new IllegalArgumentException("Invalid quantity");
    BigDecimal left = quantity, value = BigDecimal.ZERO, fee = BigDecimal.ZERO;
    for (var e : (buy ? levels : levels.descendingMap()).entrySet()) {
      if (buy ? e.getKey().compareTo(limit) > 0 : e.getKey().compareTo(limit) < 0) break;
      if (e.getValue().signum() < 0) throw new IllegalArgumentException("Negative depth");
      BigDecimal take = left.min(e.getValue());
      value = value.add(take.multiply(e.getKey()));
      fee = fee.add(fees.fee(take, e.getKey(), false));
      left = left.subtract(take);
      if (left.signum() == 0) break;
    }
    if (left.signum() > 0) throw new IllegalStateException("Insufficient depth for FOK");
    return new Result(quantity, value, fee, value.divide(quantity, 12, RoundingMode.HALF_EVEN));
  }
}
