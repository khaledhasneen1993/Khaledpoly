package com.polybot.ingestor.polymarket;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
@RequiredArgsConstructor
@Slf4j
public class PolymarketDataApiClient {

  private final @NonNull @Qualifier("polymarketDataApiRestClient") RestClient
      polymarketDataApiRestClient;
  private final @NonNull ObjectMapper objectMapper;

  public ArrayNode getTrades(String userAddress, int limit, int offset) {
    return getArray("/trades", userAddress, limit, offset);
  }

  public ArrayNode getPositions(String userAddress, int limit, int offset) {
    return getArray("/positions", userAddress, limit, offset);
  }

  public ArrayNode getMarketTrades(String marketSlug, int limit, int offset) {
    // Public trades are condition-selected; a slug is not a condition ID.
    if (marketSlug == null || !marketSlug.matches("0x[0-9a-fA-F]{64}"))
      throw new IllegalArgumentException("V2 market trades require a condition ID, not a slug");
    return fetch("/v2/trades", "condition", marketSlug, limit, offset);
  }

  private ArrayNode getArray(String path, String userAddress, int limit, int offset) {
    return fetch("/v2" + path, "user", userAddress, limit, offset);
  }

  private ArrayNode fetch(String path, String selector, String value, int limit, int offset) {
    if (value == null || value.isBlank() || limit < 1 || limit > 1000 || offset < 0)
      throw new IllegalArgumentException("Invalid data query");
    ArrayNode result = objectMapper.createArrayNode();
    String cursor = null;
    var seen = new java.util.HashSet<String>();
    int skipped = 0;
    do {
      String current = cursor;
      String body =
          polymarketDataApiRestClient
              .get()
              .uri(
                  b -> {
                    b.path(path).queryParam(selector, value).queryParam("limit", 1000);
                    if (current != null) b.queryParam("cursor", current);
                    return b.build();
                  })
              .retrieve()
              .body(String.class);
      try {
        JsonNode page = objectMapper.readTree(body);
        for (JsonNode row : com.polybot.hft.polymarket.data.DataApiV2.rows(page)) {
          if (skipped++ < offset) continue;
          if (result.size() < limit) result.add(row);
        }
        cursor = com.polybot.hft.polymarket.data.DataApiV2.next(page);
        if (cursor != null && !seen.add(cursor))
          throw new IllegalStateException("Repeated data cursor");
        if (seen.size() > 1000) throw new IllegalStateException("Pagination safety bound exceeded");
      } catch (java.io.IOException e) {
        throw new IllegalStateException("Invalid Data API v2 response", e);
      }
    } while (cursor != null && result.size() < limit);
    return result;
  }
}
