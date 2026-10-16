package com.polybot.hft.polymarket.data;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;

/** Validates V2 envelopes and exposes compatibility aliases to existing analytics consumers. */
public final class DataApiV2 {
  private DataApiV2() {}

  public static ArrayNode rows(JsonNode page) {
    JsonNode data = page.get("data");
    if (data == null || !data.isArray())
      throw new IllegalStateException("Invalid Data API v2 envelope");
    ArrayNode result = new ObjectMapper().createArrayNode();
    for (JsonNode row : data) {
      if (!row.isObject()) throw new IllegalStateException("Invalid data row");
      ObjectNode out = ((ObjectNode) row).deepCopy();
      Map<String, String> aliases =
          Map.ofEntries(
              Map.entry("proxy_wallet", "proxyWallet"),
              Map.entry("token_id", "asset"),
              Map.entry("condition_id", "conditionId"),
              Map.entry("current_size", "size"),
              Map.entry("avg_price", "avgPrice"),
              Map.entry("entry_cost_usdc", "initialValue"),
              Map.entry("current_value", "currentValue"),
              Map.entry("unrealized_pnl", "cashPnl"),
              Map.entry("realized_pnl", "realizedPnl"),
              Map.entry("current_price", "curPrice"),
              Map.entry("outcome_index", "outcomeIndex"),
              Map.entry("opposite_outcome", "oppositeOutcome"),
              Map.entry("opposite_token_id", "oppositeAsset"),
              Map.entry("negative_risk", "negativeRisk"),
              Map.entry("transaction_hash", "transactionHash"));
      aliases.forEach(
          (from, to) -> {
            if (out.has(from)) out.set(to, out.get(from));
          });
      result.add(out);
    }
    return result;
  }

  public static String next(JsonNode page) {
    JsonNode pagination = page.get("pagination");
    if (pagination == null || !pagination.isObject())
      throw new IllegalStateException("Missing cursor pagination");
    String cursor = pagination.path("next_cursor").asText(null);
    if (pagination.path("has_more").asBoolean(false) && (cursor == null || cursor.isBlank()))
      throw new IllegalStateException("Missing next cursor");
    return cursor == null || cursor.isBlank() ? null : cursor;
  }
}
