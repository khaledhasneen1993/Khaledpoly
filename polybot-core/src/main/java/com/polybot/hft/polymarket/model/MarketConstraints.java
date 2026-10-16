package com.polybot.hft.polymarket.model;

import com.fasterxml.jackson.databind.JsonNode;
import com.polybot.hft.polymarket.api.LimitOrderRequest;
import com.polybot.hft.polymarket.discovery.MarketAssetIds;
import java.math.BigDecimal;
import java.time.*;

public record MarketConstraints(
    String condition,
    String version,
    BigDecimal tick,
    BigDecimal minSize,
    boolean negativeRisk,
    Instant endTime,
    JsonNode feeSchedule) {
  public static MarketConstraints parse(JsonNode book, JsonNode market, JsonNode info) {
    String condition = book.path("market").asText();
    if (!condition.matches("0x[0-9a-fA-F]{64}")
        || !condition.equals(market.path("conditionId").asText()))
      throw new IllegalArgumentException("Market identity mismatch");
    if (!market.path("active").asBoolean(false)
        || market.path("closed").asBoolean(true)
        || !market.path("acceptingOrders").asBoolean(false)
        || market.path("archived").asBoolean(false))
      throw new IllegalStateException("Market is not accepting orders");
    if (!MarketAssetIds.parse(market).contains(book.path("asset_id").asText()))
      throw new IllegalArgumentException("Asset does not belong to market");
    BigDecimal tick = new BigDecimal(book.path("tick_size").asText()),
        min = new BigDecimal(book.path("min_order_size").asText());
    if (tick.signum() <= 0 || min.signum() <= 0)
      throw new IllegalArgumentException("Invalid constraints");
    Instant end = Instant.parse(market.path("endDate").asText());
    JsonNode fees = market.hasNonNull("feeSchedule") ? market.get("feeSchedule") : info.path("fd");
    if (market.path("feesEnabled").asBoolean(false)
        && (fees.isMissingNode() || fees.isNull() || fees.isEmpty()))
      throw new IllegalStateException("Fee parameters unavailable");
    return new MarketConstraints(
        condition,
        market.path("version").asText(),
        tick,
        min,
        book.path("neg_risk").asBoolean(false),
        end,
        fees);
  }

  public void validate(LimitOrderRequest order, Clock clock) {
    if (order.negRisk() != null && order.negRisk() != negativeRisk)
      throw new IllegalArgumentException("Negative-risk metadata mismatch");
    if ((order.feeRateBps() != null && order.feeRateBps() != 0)
        || (order.nonce() != null && order.nonce() != 0)
        || order.taker() != null)
      throw new IllegalArgumentException("Legacy signed-order fields are unsupported");
    if (!clock.instant().isBefore(endTime)) throw new IllegalStateException("Market ended");
    if (order.price() == null
        || order.size() == null
        || order.size().compareTo(minSize) < 0
        || order.price().compareTo(tick) < 0
        || order.price().compareTo(BigDecimal.ONE.subtract(tick)) > 0
        || order.price().remainder(tick).signum() != 0)
      throw new IllegalArgumentException("Order violates current market constraints");
    if (order.tickSize() != null && order.tickSize().compareTo(tick) != 0)
      throw new IllegalArgumentException("Stale tick size");
  }
}
