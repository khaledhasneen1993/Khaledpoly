package com.polybot.hft.polymarket.data;

import com.fasterxml.jackson.databind.JsonNode;
import com.polybot.hft.polymarket.http.HttpRequestFactory;
import com.polybot.hft.polymarket.http.PolymarketHttpTransport;
import java.net.URI;
import java.net.http.HttpRequest;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import lombok.NonNull;

public final class PolymarketDataApiClient {

  private static final Duration HTTP_TIMEOUT = Duration.ofSeconds(10);

  private final HttpRequestFactory requestFactory;
  private final PolymarketHttpTransport transport;

  public PolymarketDataApiClient(@NonNull URI baseUri, @NonNull PolymarketHttpTransport transport) {
    this.requestFactory = new HttpRequestFactory(Objects.requireNonNull(baseUri, "baseUri"));
    this.transport = Objects.requireNonNull(transport, "transport");
  }

  public JsonNode getTrades(String userAddress, int limit, int offset) {
    return getArray("/trades", userAddress, limit, offset);
  }

  public JsonNode getPositions(String userAddress, int limit, int offset) {
    return getArray("/positions", userAddress, limit, offset);
  }

  private JsonNode getArray(String path, String userAddress, int limit, int offset) {
    if (userAddress == null || userAddress.isBlank()) {
      throw new IllegalArgumentException("userAddress must not be blank");
    }

    if (limit < 1 || limit > 1000 || offset < 0)
      throw new IllegalArgumentException("Invalid page bounds");
    var result = new com.fasterxml.jackson.databind.ObjectMapper().createArrayNode();
    String cursor = null;
    var seen = new java.util.HashSet<String>();
    int skipped = 0;
    do {
      Map<String, String> query = new LinkedHashMap<>();
      query.put("user", userAddress);
      query.put("limit", "1000");
      query.put("include_archived", "true");
      if (cursor != null) query.put("cursor", cursor);
      HttpRequest request =
          requestFactory
              .request("/v2" + path, query)
              .GET()
              .timeout(HTTP_TIMEOUT)
              .header("Accept", "application/json")
              .build();
      JsonNode page = transport.sendJson(request, JsonNode.class);
      for (JsonNode row : DataApiV2.rows(page)) {
        if (skipped++ < offset) continue;
        if (result.size() < limit) result.add(row);
      }
      cursor = DataApiV2.next(page);
      if (cursor != null && !seen.add(cursor))
        throw new IllegalStateException("Repeated data cursor");
      if (seen.size() > 1000)
        throw new IllegalStateException("Data pagination safety bound exceeded");
    } while (cursor != null && result.size() < limit);
    return result;
  }
}
