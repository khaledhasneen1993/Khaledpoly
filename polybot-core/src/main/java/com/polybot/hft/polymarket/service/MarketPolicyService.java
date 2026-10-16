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

  public MarketConstraints resolve(String token) {
    var book = clob.getRawOrderBook(token);
    var markets = gamma.markets(Map.of("condition_ids", book.path("market").asText()), Map.of());
    if (!markets.isArray() || markets.size() != 1)
      throw new IllegalStateException("Cannot resolve unique market");
    return MarketConstraints.parse(
        book, markets.get(0), clob.getClobMarketInfo(book.path("market").asText()));
  }
}
