package com.polybot.hft.polymarket.discovery;

import com.fasterxml.jackson.databind.*;
import java.util.*;

public final class MarketAssetIds {
  private MarketAssetIds() {}

  public static List<String> parse(JsonNode market) {
    String version = market.path("version").asText();
    String field =
        switch (version) {
          case "v1" -> "clobTokenIds";
          case "v2" -> "positionIds";
          default -> throw new IllegalArgumentException("Missing/unsupported market version");
        };
    JsonNode ids = market.path(field);
    try {
      if (ids.isTextual()) ids = new ObjectMapper().readTree(ids.asText());
    } catch (java.io.IOException e) {
      throw new IllegalArgumentException("Malformed outcome IDs", e);
    }
    if (!ids.isArray() || ids.isEmpty()) throw new IllegalArgumentException("Missing outcome IDs");
    List<String> result = new ArrayList<>();
    for (JsonNode id : ids) {
      if (!id.asText().matches("[0-9]+")) throw new IllegalArgumentException("Invalid asset ID");
      result.add(id.asText());
    }
    return List.copyOf(result);
  }
}
