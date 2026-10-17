package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;

/** An empty scope means connection-wide uncertainty; known assets must remain scoped. */
public final class DataGap {
  private DataGap() {}

  public static Set<String> tokens(JsonNode data) {
    var result = new TreeSet<String>();
    if (data.has("token")) add(result, data.get("token"));
    if (data.has("tokens")) {
      if (!data.get("tokens").isArray() || data.get("tokens").size() > 128)
        throw new IllegalArgumentException("Invalid gap token scope");
      for (var token : data.get("tokens")) add(result, token);
    }
    return Set.copyOf(result);
  }

  private static void add(Set<String> result, JsonNode token) {
    if (!token.isTextual() || token.asText().isBlank() || token.asText().length() > 256)
      throw new IllegalArgumentException("Invalid gap token");
    result.add(token.asText());
  }

  public static Set<String> messageTokens(JsonNode node) {
    var tokens = new TreeSet<String>();
    if (node.hasNonNull("asset_id") && !node.path("asset_id").asText().isBlank())
      tokens.add(node.path("asset_id").asText());
    for (var change : node.path("price_changes"))
      if (!change.path("asset_id").asText().isBlank()) tokens.add(change.path("asset_id").asText());
    if (tokens.size() > 128) throw new IllegalArgumentException("Oversized source token scope");
    return tokens;
  }
}
