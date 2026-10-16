package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.polymarket.ws.LocalOrderBook;
import java.util.*;
import java.util.function.BiConsumer;

/**
 * Decode raw ingestor frames without replacing source timestamps or manufacturing missing
 * snapshots.
 */
public final class RawTapeNormalizer {
  private final ObjectMapper mapper;
  private final Map<String, LocalOrderBook> books = new HashMap<>();
  private final Map<String, Long> stamps = new HashMap<>();

  public RawTapeNormalizer(ObjectMapper mapper) {
    this.mapper = mapper;
  }

  public void accept(String text, long arrival, BiConsumer<String, JsonNode> output)
      throws java.io.IOException {
    if (text.equals("PING") || text.equals("PONG")) return;
    JsonNode root = mapper.readTree(text);
    if (root.isArray()) {
      for (var n : root) one(n, arrival, output);
    } else one(root, arrival, output);
  }

  private void one(JsonNode n, long arrival, BiConsumer<String, JsonNode> out) {
    String type = n.path("event_type").asText();
    if (!Set.of("book", "price_change", "last_trade_price", "tick_size_change").contains(type))
      return;
    long stamp = n.path("timestamp").asLong(-1);
    if (stamp > 0 && stamp < 100000000000L) stamp *= 1000;
    if (stamp < 0 || stamp > arrival || arrival - stamp > 2000) {
      gap(out, "stale_source");
      return;
    }
    if (type.equals("price_change")) {
      for (var change : n.path("price_changes")) {
        String t = change.path("asset_id").asText();
        if (stamp < stamps.getOrDefault(t, -1L)) {
          gap(out, "source_regression");
          return;
        }
        var b = books.get(t);
        if (b == null) {
          gap(out, "delta_without_snapshot");
          return;
        }
        b.change(
            change.path("side").asText(),
            PaperMatchingEngine.decimal(change, "price"),
            PaperMatchingEngine.decimal(change, "size"));
        stamps.put(t, stamp);
        emitBook(t, b, stamp, out);
      }
    } else if (type.equals("book")) {
      String t = PaperMatchingEngine.required(n, "asset_id");
      if (stamp < stamps.getOrDefault(t, -1L)) {
        gap(out, "source_regression");
        return;
      }
      var b = new LocalOrderBook();
      b.snapshot(
          n.has("bids") ? n.get("bids") : n.path("buys"),
          n.has("asks") ? n.get("asks") : n.path("sells"));
      books.put(t, b);
      stamps.put(t, stamp);
      emitBook(t, b, stamp, out);
    } else if (type.equals("tick_size_change"))
      out.accept(
          "TICK_SIZE",
          mapper.valueToTree(
              Map.of(
                  "token",
                  n.path("asset_id").asText(),
                  "tick",
                  n.path("new_tick_size").asText(),
                  "sourceMs",
                  stamp)));
    else if (type.equals("last_trade_price"))
      out.accept(
          "TRADE",
          mapper.valueToTree(
              Map.of(
                  "token",
                  n.path("asset_id").asText(),
                  "side",
                  n.path("side").asText(),
                  "price",
                  n.path("price").asText(),
                  "size",
                  n.path("size").asText(),
                  "tradeId",
                  n.toString(),
                  "sourceMs",
                  stamp)));
  }

  private void emitBook(
      String token, LocalOrderBook book, long stamp, BiConsumer<String, JsonNode> out) {
    var data = new HashMap<String, Object>(book.depth());
    data.put("token", token);
    data.put("sourceMs", stamp);
    out.accept("BOOK", mapper.valueToTree(data));
  }

  private void gap(BiConsumer<String, JsonNode> out, String reason) {
    books.clear();
    stamps.clear();
    out.accept("GAP", mapper.valueToTree(Map.of("reason", reason)));
  }

  public void reset() {
    books.clear();
    stamps.clear();
  }
}
