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
    if (text.equalsIgnoreCase("PING") || text.equalsIgnoreCase("PONG")) return;
    var pending = new ArrayList<Map.Entry<String, JsonNode>>();
    BiConsumer<String, JsonNode> collect = (kind, data) -> pending.add(Map.entry(kind, data));
    try {
      JsonNode root = mapper.readTree(text);
      if (root != null && root.isArray()) {
        for (var n : root) one(n, arrival, collect);
      } else one(root, arrival, collect);
    } catch (Exception invalid) {
      // Streaming rejects the whole frame on a malformed full snapshot or message.
      // Never expose the earlier half of that frame to a strategy.
      gap(output, "invalid_message");
      return;
    }
    pending.forEach(event -> output.accept(event.getKey(), event.getValue()));
  }

  private void one(JsonNode n, long arrival, BiConsumer<String, JsonNode> out) {
    if (n == null || n.isNull()) return;
    String type = n.path("event_type").asText();
    if (!Set.of("book", "price_change", "last_trade_price", "tick_size_change").contains(type))
      return;
    long stamp = n.path("timestamp").asLong(-1);
    if (stamp > 0 && stamp < 100000000000L) stamp *= 1000;
    boolean fresh = stamp >= 0 && arrival - stamp >= 0 && arrival - stamp <= 2000;
    // The streaming adapter drops stale historical trade notifications without invalidating depth.
    if (type.equals("last_trade_price") && !fresh) return;
    if ((type.equals("book") || type.equals("price_change")) && !fresh) {
      String token = n.path("asset_id").asText(null);
      if (token != null) books.remove(token);
      else books.clear();
      out.accept("GAP", mapper.valueToTree(Map.of("reason", "stale_source", "sourceMs", stamp)));
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
        // Match streaming: a delta cannot reconstruct missing depth; wait for a full snapshot.
        if (b == null) continue;
        try {
          b.changes(batch.getValue());
        } catch (RuntimeException e) {
          invalidateToken(t, stamp, out, "invalid_depth");
          continue;
        }
        emitBook(t, b, stamp, out);
      }
    } else if (type.equals("book")) {
      String t = PaperMatchingEngine.required(n, "asset_id");
      if (stamp < stamps.getOrDefault(t, -1L)) return;
      stamps.put(t, stamp);
      var b = new LocalOrderBook();
      b.snapshot(
          n.has("bids") ? n.get("bids") : n.path("buys"),
          n.has("asks") ? n.get("asks") : n.path("sells"));
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

  private void invalidateToken(
      String token, long stamp, BiConsumer<String, JsonNode> out, String reason) {
    books.remove(token);
    if (awaitingSnapshots.add(token))
      out.accept(
          "GAP", mapper.valueToTree(Map.of("reason", reason, "token", token, "sourceMs", stamp)));
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
