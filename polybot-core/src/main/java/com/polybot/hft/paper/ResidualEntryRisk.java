package com.polybot.hft.paper;

import java.math.BigDecimal;

/** Pure entry veto. Does not alter quantity, execution, fees, limits or exit behavior. */
final class ResidualEntryRisk {
  static boolean allows(boolean enabled,BigDecimal quantity,BigDecimal first,BigDecimal second,
      BigDecimal budget,BigDecimal redemptionCost) {
    if (quantity==null || first==null || second==null || budget==null || redemptionCost==null
        || quantity.signum()<=0 || first.signum()<=0 || first.compareTo(BigDecimal.ONE)>=0
        || second.signum()<=0 || second.compareTo(BigDecimal.ONE)>=0
        || budget.signum()<0 || redemptionCost.signum()<0)
      throw new IllegalArgumentException("Invalid residual entry risk inputs");
    return !enabled || quantity.multiply(first.max(second)).add(redemptionCost).compareTo(budget)<=0;
  }
}
