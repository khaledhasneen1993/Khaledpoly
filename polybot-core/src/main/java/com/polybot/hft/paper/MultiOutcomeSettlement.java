package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.polymarket.discovery.MarketAssetIds;
import java.math.BigDecimal;
import java.util.*;

/**
 * Terminal, mutually exclusive negative-risk events. Virtual accounting only; no
 * conversion/signing.
 */
public final class MultiOutcomeSettlement {
  public record Verified(
      String event, String membershipSha256, Map<String, Map<String, BigDecimal>> payouts) {}

  private MultiOutcomeSettlement() {}

  public static Verified verify(
      JsonNode event,
      Map<String, ResearchMarket> markets,
      Map<String, ResolutionEvidence> resolutions,
      ObjectMapper mapper) {
    String id = event.path("id").asText();
    if (!id.matches("[0-9]{1,24}")
        || !event.path("closed").asBoolean()
        || !event.path("negRisk").asBoolean()
        || event.path("negRiskAugmented").asBoolean(false)
        || !event.path("markets").isArray()
        || event.path("markets").size() < 2
        || event.path("markets").size() > 16)
      throw new IllegalArgumentException("Incomplete, nonterminal or augmented outcome universe");
    var vectors = new TreeMap<String, Map<String, BigDecimal>>();
    var names = new HashSet<String>();
    var tokens = new HashSet<String>();
    int winners = 0;
    var identity = new TreeMap<String, Object>();
    for (var row : event.path("markets")) {
      String condition = row.path("conditionId").asText(),
          name = row.path("groupItemTitle").asText();
      ResearchMarket market = markets.get(condition);
      ResolutionEvidence resolution = resolutions.get(condition);
      if (market == null
          || !market.negativeRisk()
          || resolution == null
          || name.isBlank()
          || !names.add(name)
          || vectors.containsKey(condition))
        throw new IllegalArgumentException("Missing member identity or terminal evidence");
      JsonNode ids = row;
      if (!row.hasNonNull("version")
          && row.hasNonNull("clobTokenIds")
          && !row.hasNonNull("positionIds")) {
        var copy = (com.fasterxml.jackson.databind.node.ObjectNode) row.deepCopy();
        copy.put("version", "v1");
        ids = copy;
      }
      var assets = MarketAssetIds.parse(ids);
      JsonNode outcomes = row.path("outcomes");
      try {
        if (outcomes.isTextual()) outcomes = mapper.readTree(outcomes.asText());
      } catch (Exception e) {
        throw new IllegalArgumentException("Invalid outcome labels", e);
      }
      if (assets.size() != 2
          || !assets.get(0).equals(market.first())
          || !assets.get(1).equals(market.second())
          || outcomes.size() != 2
          || !outcomes.get(0).asText().equalsIgnoreCase("Yes")
          || !outcomes.get(1).asText().equalsIgnoreCase("No")
          || !tokens.add(market.first())
          || !tokens.add(market.second()))
        throw new IllegalArgumentException("Unknown YES/NO slots or shared tokens");
      var yes = resolution.payouts().get(market.first());
      if (yes.compareTo(BigDecimal.ONE) == 0) winners++;
      else if (yes.signum() != 0)
        throw new IllegalArgumentException("Disputed/fractional event requires separate review");
      vectors.put(condition, resolution.payouts());
      identity.put(condition, Map.of("name", name, "tokens", assets));
    }
    if (winners != 1)
      throw new IllegalArgumentException("Terminal event does not have exactly one winner");
    try {
      String hash =
          java.util.HexFormat.of()
              .formatHex(
                  java.security.MessageDigest.getInstance("SHA-256")
                      .digest(
                          mapper
                              .writer()
                              .with(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
                              .writeValueAsBytes(identity)));
      return new Verified(id, hash, Map.copyOf(vectors));
    } catch (Exception e) {
      throw new IllegalStateException("Cannot hash terminal universe", e);
    }
  }
}
