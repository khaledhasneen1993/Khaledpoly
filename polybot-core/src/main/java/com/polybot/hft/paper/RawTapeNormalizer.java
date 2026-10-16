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
  private final Set<String> awaitingSnapshots = new HashSet<>();

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
      var batches = new LinkedHashMap<String, com.fasterxml.jackson.databind.node.ArrayNode>();
      for (var change : n.path("price_changes"))
        batches
            .computeIfAbsent(change.path("asset_id").asText(), k -> mapper.createArrayNode())
            .add(change);
      for (var batch : batches.entrySet()) {
        String t = batch.getKey();
        // Match the streaming adapter: older observations cannot replace newer state.
        if (stamp < stamps.getOrDefault(t, -1L)) continue;
        stamps.put(t, stamp);
        var b = books.get(t);
        if (b == null) {
          invalidateToken(t, out, "delta_without_snapshot");
          continue;
        }
        try {
          b.changes(batch.getValue());
        } catch (RuntimeException e) {
          invalidateToken(t, out, "invalid_depth");
          continue;
        }
        emitBook(t, b, stamp, out);
      }
    } else if (type.equals("book")) {
      String t = PaperMatchingEngine.required(n, "asset_id");
      if (stamp < stamps.getOrDefault(t, -1L)) return;
      stamps.put(t, stamp);
      var b = new LocalOrderBook();
      try {
        b.snapshot(
            n.has("bids") ? n.get("bids") : n.path("buys"),
            n.has("asks") ? n.get("asks") : n.path("sells"));
      } catch (RuntimeException e) {
        invalidateToken(t, out, "invalid_depth");
        return;
      }
      books.put(t, b);
      awaitingSnapshots.remove(t);
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

  private void invalidateToken(String token, BiConsumer<String, JsonNode> out, String reason) {
    books.remove(token);
    if (awaitingSnapshots.add(token))
      out.accept("GAP", mapper.valueToTree(Map.of("reason", reason, "token", token)));
  }

  private void gap(BiConsumer<String, JsonNode> out, String reason) {
    books.clear();
    awaitingSnapshots.clear();
    out.accept("GAP", mapper.valueToTree(Map.of("reason", reason)));
  }

  public void reset() {
    books.clear();
    stamps.clear();
    awaitingSnapshots.clear();
  }
}
