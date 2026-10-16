package com.polybot.hft.polymarket.model;

import java.util.Locale;
import java.util.Set;

public final class OrderStatus {
  private OrderStatus() {}

  public static boolean terminal(String status) {
    return status != null
        && Set.of(
                "FILLED",
                "MATCHED",
                "CANCELED",
                "CANCELLED",
                "EXPIRED",
                "REJECTED",
                "FAILED",
                "DONE",
                "CLOSED")
            .contains(status.trim().toUpperCase(Locale.ROOT));
  }
}
