package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import com.polybot.hft.state.AtomicJsonState;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.util.*;

/** Durable, idempotent shadow screening. No reference to an order-submission API exists here. */
public final class ResearchProposalInbox implements AutoCloseable {
  private final ObjectMapper mapper;
  private final AtomicJsonState file;
  private ObjectNode state;

  public ResearchProposalInbox(ObjectMapper mapper, Path path) {
    this.mapper = mapper;
    file = new AtomicJsonState(path, mapper);
    var loaded = file.load();
    if (loaded != null
        && (loaded.path("version").asInt() != 1 || !loaded.path("receipts").isObject()))
      throw new IllegalStateException("Unknown proposal inbox state");
    state = loaded == null ? mapper.createObjectNode() : (ObjectNode) loaded;
    if (loaded == null) {
      state.put("version", 1);
      state.set("receipts", mapper.createObjectNode());
    }
  }

  public synchronized JsonNode screen(JsonNode snapshot, JsonNode proposal) {
    if (!snapshot.path("mode").asText().equals("PAPER")
        || snapshot.path("liveAllowed").asBoolean(true)
        || snapshot.path("executionEnabled").asBoolean(true)
        || snapshot.path("truncated").asBoolean(true))
      throw new IllegalStateException("PAPER observation required");
    proposal = canonical(proposal);
    String id = proposal.path("id").asText();
    if (!id.matches("[A-Za-z0-9_.:-]{1,128}")
        || !proposal.path("strategy").isTextual()
        || proposal.path("strategy").asText().isBlank()
        || !proposal.path("legs").isArray()
        || proposal.path("legs").isEmpty()
        || proposal.path("legs").size() > 16)
      throw new IllegalArgumentException("Invalid proposal contract");
    if (!proposal.path("sessionId").equals(snapshot.path("sessionId"))
        || !proposal.path("accountId").asText().equals(snapshot.path("account").path("id").asText())
        || !proposal.path("sequence").isIntegralNumber()
        || !proposal.path("sequence").canConvertToLong()
        || proposal.path("sequence").asLong() != snapshot.path("sequence").asLong())
      throw new IllegalStateException("Stale proposal generation or wrong account");
    var receipts = state.withObject("/receipts");
    if (receipts.has(id)) {
      if (!receipts.path(id).path("request").equals(proposal))
        throw new IllegalStateException("Proposal id reused with different content");
      return receipts.path(id).path("response").deepCopy();
    }
    if (receipts.size() >= 10000)
      throw new IllegalStateException("Inbox full; archive before a new research account");
    var next = state.deepCopy();
    String generation =
        snapshot.path("sessionId").asText() + ":" + snapshot.path("sequence").asLong();
    if (!generation.equals(next.path("generation").asText())) {
      next.put("generation", generation).put("reserved", "0");
      next.set("groups", mapper.createObjectNode());
      next.set("tokens", mapper.createArrayNode());
    }
    var account = snapshot.path("account");
    if (account.path("halted").asBoolean(true) || account.path("pendingTakers").asInt(-1) != 0)
      throw new IllegalStateException("Account risk actions pending or halted");
    long now = snapshot.path("generatedMs").asLong();
    BigDecimal cash = decimal(account, "availableCash").subtract(decimal(next, "reserved"));
    BigDecimal total = decimal(next, "reserved"), cost = BigDecimal.ZERO;
    var groups = next.withObject("/groups");
    var tokens = new HashSet<String>();
    next.path("tokens").forEach(t -> tokens.add(t.asText()));
    for (var holding : account.path("holdings")) total = total.add(decimal(holding, "basis"));
    for (var order : account.path("orders"))
      if (order.path("buy").asBoolean())
        total = total.add(decimal(order, "price").multiply(decimal(order, "remaining")));
    long expiry = Long.MAX_VALUE;
    for (var item : proposal.path("legs")) {
      String token = item.path("token").asText(), condition = item.path("condition").asText();
      JsonNode market = null;
      for (var m : snapshot.path("markets"))
        if (m.path("condition").asText().equals(condition)) market = m;
      if (market == null
          || !(token.equals(market.path("first").asText())
              || token.equals(market.path("second").asText())))
        throw new IllegalArgumentException("Unknown market token");
      var book = snapshot.path("books").path(token);
      long source = book.path("sourceMs").asLong(-1), age = snapshot.path("maxBookAgeMs").asLong();
      long expires = item.path("expiresMs").asLong(-1);
      if (!market.path("accepting").asBoolean()
          || now < market.path("startMs").asLong()
          || now >= market.path("endMs").asLong()
          || now - market.path("observedMs").asLong() > snapshot.path("metadataMaxAgeMs").asLong()
          || source < 0
          || source > now
          || now - source >= age
          || book.path("depthTruncated").asBoolean(true)
          || book.path("bids").isEmpty()
          || book.path("asks").isEmpty()
          || expires <= now
          || expires > Math.min(source + age, market.path("endMs").asLong())
          || !tokens.add(token))
        throw new IllegalStateException("Unavailable market, expiry or duplicate token");
      for (var order : account.path("orders"))
        if (order.path("token").asText().equals(token) && decimal(order, "remaining").signum() > 0)
          throw new IllegalStateException("Token already reserved by executor");
      BigDecimal price = decimal(item, "price"),
          size = decimal(item, "size"),
          value = price.multiply(size);
      boolean buy = item.path("buy").asBoolean();
      if (!item.path("buy").isBoolean()
          || price.signum() <= 0
          || price.compareTo(BigDecimal.ONE) >= 0
          || size.compareTo(decimal(market, "minSize")) < 0
          || price.remainder(decimal(market, "tick")).signum() != 0
          || value.compareTo(new BigDecimal("25")) > 0
          || (buy && price.compareTo(decimal(book.path("asks").get(0), "price")) >= 0)
          || (!buy && price.compareTo(decimal(book.path("bids").get(0), "price")) <= 0))
        throw new IllegalArgumentException("Invalid passive quote");
      if (buy) {
        cost = cost.add(value);
        BigDecimal group = groups.has(condition) ? decimal(groups, condition) : BigDecimal.ZERO;
        for (String t : List.of(market.path("first").asText(), market.path("second").asText())) {
          if (account.path("holdings").has(t))
            group = group.add(decimal(account.path("holdings").path(t), "basis"));
          for (var o : account.path("orders"))
            if (o.path("token").asText().equals(t) && o.path("buy").asBoolean())
              group = group.add(decimal(o, "price").multiply(decimal(o, "remaining")));
        }
        if (group.add(value).compareTo(new BigDecimal("25")) > 0)
          throw new IllegalStateException("Market exposure limit");
        groups.put(
            condition,
            (groups.has(condition) ? decimal(groups, condition) : BigDecimal.ZERO)
                .add(value)
                .toPlainString());
      } else if (!account.path("holdings").has(token)
          || size.compareTo(decimal(account.path("holdings").path(token), "shares")) > 0)
        throw new IllegalStateException("Uncovered sell");
      expiry = Math.min(expiry, expires);
    }
    if (cost.compareTo(cash) > 0 || total.add(cost).compareTo(new BigDecimal("100")) > 0)
      throw new IllegalStateException("Cash or portfolio exposure limit");
    next.put("reserved", decimal(next, "reserved").add(cost).toPlainString());
    var used = mapper.createArrayNode();
    tokens.stream().sorted().forEach(used::add);
    next.set("tokens", used);
    var response = mapper.createObjectNode();
    response
        .put("id", id)
        .put("status", "SCREENED_SHADOW_ONLY")
        .put("sequence", snapshot.path("sequence").asLong())
        .put("expiresMs", expiry)
        .put("executionEnabled", false)
        .put("liveAllowed", false)
        .put("decision", "NO_GO");
    var receipt = mapper.createObjectNode();
    receipt.set("request", proposal.deepCopy());
    receipt.set("response", canonical(response));
    next.withObject("/receipts").set(id, receipt);
    file.save(next);
    state = next;
    return canonical(response);
  }

  private JsonNode canonical(JsonNode node) {
    try {
      return mapper.readTree(node.toString());
    } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
      throw new IllegalArgumentException("Invalid JSON", e);
    }
  }

  private static BigDecimal decimal(JsonNode node, String key) {
    if (!node.hasNonNull(key) || node.path(key).isBoolean())
      throw new IllegalArgumentException("Missing decimal " + key);
    return new BigDecimal(node.path(key).asText());
  }

  public synchronized void close() {
    file.close();
  }
}
