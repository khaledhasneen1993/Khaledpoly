package com.polybot.hft.polymarket.service;

import com.polybot.hft.polymarket.clob.PolymarketClobClient;
import com.polybot.hft.polymarket.gamma.PolymarketGammaClient;
import com.polybot.hft.polymarket.model.MarketConstraints;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class MarketPolicyService {
  private final PolymarketClobClient clob;
  private final PolymarketGammaClient gamma;

  public boolean binaryPair(String up, String down) {
    var book = clob.getRawOrderBook(up);
    var markets = gamma.markets(Map.of("condition_ids", book.path("market").asText()), Map.of());
    if (!markets.isArray() || markets.size() != 1) return false;
    var tokens = com.polybot.hft.polymarket.discovery.MarketAssetIds.parse(markets.get(0));
    return tokens.size() == 2 && !up.equals(down) && tokens.contains(up) && tokens.contains(down);
  }

  private record Cached(long at, MarketConstraints constraints) {}

  private final java.util.Map<String, Cached> cache =
      new java.util.concurrent.ConcurrentHashMap<>();

  public MarketConstraints resolve(String token) {
    long now = System.currentTimeMillis();
    var existing = cache.get(token);
    if (existing != null && now - existing.at() < 2000) return existing.constraints();
    var book = clob.getRawOrderBook(token);
    var markets = gamma.markets(Map.of("condition_ids", book.path("market").asText()), Map.of());
    if (!markets.isArray() || markets.size() != 1)
      throw new IllegalStateException("Cannot resolve unique market");
    int baseFee = clob.getBaseFeeBps(token);
    if (baseFee < 0) throw new IllegalStateException("Invalid fee rate");
    var constraints =
        MarketConstraints.parse(
            book, markets.get(0), clob.getClobMarketInfo(book.path("market").asText()));
    cache.put(token, new Cached(now, constraints));
    return constraints;
  }
}
