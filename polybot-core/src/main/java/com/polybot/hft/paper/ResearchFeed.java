package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.polymarket.discovery.MarketAssetIds;
import com.polybot.hft.polymarket.ws.ClobMarketWebSocketClient;
import jakarta.annotation.*;
import java.math.*;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Public-data ingestor; keeps expired conditions until their explicit terminal payouts arrive. */
@Component
public class ResearchFeed {
  private final HttpClient http;
  private final ObjectMapper mapper;
  private final Clock clock;
  private final PaperJournal journal;
  private final ClobMarketWebSocketClient ws;
  private final List<java.util.function.Consumer<Input>> listeners = new CopyOnWriteArrayList<>();
  private final Map<String, ResearchMarket> markets =
      new java.util.concurrent.ConcurrentHashMap<>();
  private final Set<String> resolved = java.util.concurrent.ConcurrentHashMap.newKeySet();

  @Value("${paper.market-data.enabled:false}")
  private boolean enabled;

  @Value("${paper.universe.five-minute:false}")
  private boolean five;

  @Value("${paper.universe.fifteen-minute:true}")
  private boolean fifteen;

  @Value("${paper.universe.hourly:true}")
  private boolean hourly;

  private volatile boolean stopping;

  @PreDestroy
  void stop() {
    try {
      if (enabled) ws.stopAndDrainFrames();
    } finally {
      stopping = true;
    }
  }

  @Value("${paper.phase3.execution.enabled:false}")
  private boolean externalPaper;

  @Value("${paper.phase3.discovery.tags:}")
  private String broaderTags = "";

  private final Map<String, JsonNode> outcomeGroups =
      new java.util.concurrent.ConcurrentHashMap<>();

  private volatile long retryAfter;
  private long failures;

  public ResearchFeed(
      HttpClient http,
      ObjectMapper mapper,
      Clock clock,
      PaperJournal journal,
      ClobMarketWebSocketClient ws) {
    this.http = http;
    this.mapper = mapper;
    this.clock = clock;
    this.journal = journal;
    this.ws = ws;
  }

  public synchronized <T> T readConsistently(java.util.function.Supplier<T> reader) {
    return reader.get();
  }

  /** External PAPER input shares the same receive-order lock as market frames. */
  public synchronized void publishPaperProposal(JsonNode proposal) {
    if (stopping) throw new IllegalStateException("Research feed unavailable");
    emit("EXTERNAL_PROPOSAL", proposal.deepCopy());
  }

  public void retireOutcomeGroup(String id) {
    outcomeGroups.remove(id);
  }

  public void recoverGroups(List<JsonNode> groups) {
    groups.forEach(g -> outcomeGroups.put(g.path("id").asText(), g.deepCopy()));
  }

  public void publishPaperGroupSettlement(String id) {
    if (!id.matches("[0-9]{1,24}") || stopping || clock.millis() < retryAfter)
      throw new IllegalArgumentException("Invalid group or public API backoff");
    try {
      JsonNode event = get("https://gamma-api.polymarket.com/events/" + id);
      if (!event.path("id").asText().equals(id))
        throw new IllegalArgumentException("Event identity mismatch");
      emit("GROUP_SETTLEMENT", event);
    } catch (RuntimeException e) {
      throw e;
    } catch (Exception e) {
      throw new IllegalStateException("Cannot read terminal event", e);
    }
  }

  public record Input(String kind, long at, JsonNode data) {}

  public void listen(java.util.function.Consumer<Input> listener) {
    listeners.add(listener);
  }

  public void recover(List<ResearchMarket> rows) {
    rows.forEach(m -> markets.putIfAbsent(m.condition(), m));
  }

  private synchronized void emit(String kind, JsonNode data) {
    if (stopping) return;
    long at =
        journal.record(
            "RESEARCH_" + kind, data.has("sourceMs") ? data.path("sourceMs").asLong() : null, data);
    for (var l : listeners) l.accept(new Input(kind, at, data));
  }

  @PostConstruct
  void start() {
    if (enabled) {
      journal.record(
          "DATASET_CONFIG",
          null,
          Map.of(
              "schema",
              1,
              "format",
              "normalized-public-v2",
              "strategyIndependent",
              !externalPaper));
      ws.onFrame(this::emit);
    }
  }

  @Scheduled(initialDelay = 250, fixedDelay = 250, scheduler = "paperClockScheduler")
  public void tick() {
    if (enabled) emit("TICK", mapper.createObjectNode());
  }

  @Scheduled(initialDelay = 1000, fixedDelay = 15000)
  public void poll() {
    if (!enabled || clock.millis() < retryAfter) return;
    try {
      long sent = clock.millis();
      JsonNode server = get("https://clob.polymarket.com/time");
      long received = clock.millis();
      long serverMs =
          server.isNumber() ? server.asLong() * 1000 : server.path("timestamp").asLong(-1) * 1000;
      if (serverMs <= 0) throw new IllegalArgumentException("Unknown venue clock response");
      long clockOffset = serverMs - (sent + received) / 2;
      journal.record(
          "CLOCK_SYNC", serverMs, Map.of("offsetMs", clockOffset, "rttMs", received - sent));
      if (Math.abs(clockOffset) > 1000 + (received - sent) / 2)
        throw new IllegalStateException("Venue clock offset too large");
      Instant now = clock.instant();
      var slugs = new ArrayList<String>();
      for (String asset : List.of("btc", "eth"))
        for (int seconds : List.of(300, 900))
          if (seconds == 300 ? five : fifteen) {
            long start = Math.floorDiv(now.getEpochSecond(), seconds) * seconds;
            for (int offset : new int[] {-1, 0, 1})
              slugs.add(asset + "-updown-" + (seconds / 60) + "m-" + (start + offset * seconds));
          }
      if (hourly) {
        var et =
            now.atZone(ZoneId.of("America/New_York"))
                .truncatedTo(java.time.temporal.ChronoUnit.HOURS);
        for (String asset : List.of("bitcoin", "ethereum"))
          for (int offset : new int[] {0, 1}) {
            var t = et.plusHours(offset);
            int h = t.getHour() % 12;
            if (h == 0) h = 12;
            slugs.add(
                asset
                    + "-up-or-down-"
                    + t.getMonth()
                        .getDisplayName(java.time.format.TextStyle.FULL, Locale.ENGLISH)
                        .toLowerCase(Locale.ROOT)
                    + "-"
                    + t.getDayOfMonth()
                    + "-"
                    + h
                    + (t.getHour() < 12 ? "am" : "pm")
                    + "-et");
          }
      }
      for (String slug : slugs) discover(slug);
      if (externalPaper && !broaderTags.isBlank()) discoverBroader();
      if (externalPaper)
        for (var entry : List.copyOf(outcomeGroups.entrySet())) {
          JsonNode event = get("https://gamma-api.polymarket.com/events/" + entry.getKey());
          if (!event.path("id").asText().equals(entry.getKey()))
            throw new IllegalArgumentException("Event identity mismatch");
          emit("GROUP_META", event);
          if (event.path("closed").asBoolean()) emit("GROUP_SETTLEMENT", event);
        }
      var active = new TreeSet<String>();
      for (var m : markets.values())
        if (!resolved.contains(m.condition())
            && clock.millis() >= m.startMs()
            && clock.millis() < m.endMs()) {
          active.add(m.first());
          active.add(m.second());
        }
      if (!active.isEmpty()) ws.setSubscribedAssets(List.copyOf(active));
      List<String> conditions =
          markets.keySet().stream().filter(c -> !resolved.contains(c)).sorted().toList();
      for (int i = 0; i < conditions.size(); i += 20) {
        String selected =
            String.join(",", conditions.subList(i, Math.min(i + 20, conditions.size())));
        JsonNode result = get(ResolutionEvidence.SOURCE + "?condition=" + selected);
        if (!result.path("data").isArray())
          throw new IllegalArgumentException("Invalid resolution envelope");
        for (var row : result.path("data"))
          if (row.path("status").asText().equals("resolved")) {
            var m = markets.get(row.path("condition_id").asText());
            if (m == null) throw new IllegalArgumentException("Unexpected resolution condition");
            ResolutionEvidence.parse(m, row, clock.millis());
            emit("RESOLUTION", row);
            resolved.add(m.condition());
          }
      }
      failures = 0;
    } catch (Exception e) {
      failures++;
      retryAfter =
          Math.max(retryAfter, clock.millis() + Math.min(60000, 1000L << Math.min(failures, 6)));
      emit(
          "FEED_ERROR",
          mapper.valueToTree(
              Map.of(
                  "message",
                  e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()),
                  "retryAfter",
                  retryAfter)));
    }
  }

  private void discoverBroader() throws Exception {
    for (String tag : broaderTags.split(",")) {
      tag = tag.trim();
      if (!Set.of("politics", "sports").contains(tag))
        throw new IllegalArgumentException("Unsupported discovery tag");
      JsonNode resolved = get("https://gamma-api.polymarket.com/tags/slug/" + tag);
      if (!resolved.path("slug").asText().equals(tag)
          || !resolved.path("id").asText().matches("[0-9]+"))
        throw new IllegalArgumentException("Tag identity mismatch");
      JsonNode page =
          get(
              "https://gamma-api.polymarket.com/events/keyset?closed=false&limit=3&tag_id="
                  + resolved.path("id").asText());
      if (!page.path("events").isArray() || page.path("events").size() > 3)
        throw new IllegalArgumentException("Discovery page bound");
      for (var listed : page.path("events")) {
        String eventId = listed.path("id").asText();
        if (!eventId.matches("[0-9]{1,24}")) throw new IllegalArgumentException("Missing event id");
        JsonNode event = get("https://gamma-api.polymarket.com/events/" + eventId);
        if (!event.path("id").asText().equals(eventId))
          throw new IllegalArgumentException("Event detail identity mismatch");
        if (!event.path("markets").isArray()
            || event.path("markets").size() > 16
            || event.path("negRiskAugmented").asBoolean(false)) continue;
        if (event.path("negRisk").asBoolean() && event.path("markets").size() >= 2) {
          String id = event.path("id").asText();
          if (!id.matches("[0-9]{1,24}"))
            throw new IllegalArgumentException("Event identity missing");
          if (outcomeGroups.size() >= 32 && !outcomeGroups.containsKey(id)) continue;
          outcomeGroups.put(id, event.deepCopy());
          emit("GROUP_META", event);
        }
        for (var row : event.path("markets")) {
          try {
            metadata(row);
          } catch (PublicApiFailure e) {
            if (e.status != 404) throw e;
            emit(
                "MARKET_UNAVAILABLE",
                mapper.valueToTree(
                    Map.of(
                        "condition",
                        row.path("conditionId").asText(),
                        "url",
                        e.url,
                        "status",
                        404)));
          } catch (IllegalArgumentException | java.time.DateTimeException e) {
            emit(
                "MARKET_UNAVAILABLE",
                mapper.valueToTree(
                    Map.of(
                        "condition", row.path("conditionId").asText(), "reason", e.getMessage())));
          }
        }
      }
    }
  }

  private void discover(String slug) throws Exception {
    String condition =
        markets.values().stream()
            .filter(m -> m.evidence().endsWith("slug=" + slug))
            .map(ResearchMarket::condition)
            .findFirst()
            .orElse("");
    try {
      JsonNode list = get("https://gamma-api.polymarket.com/markets?slug=" + slug);
      if (list.isArray() && list.size() == 1) {
        condition = list.get(0).path("conditionId").asText("");
        metadata(list.get(0));
      }
    } catch (PublicApiFailure e) {
      // A disappearing/unscheduled book cannot starve the rest of the universe.
      // Global transport, rate-limit and server failures still stop this poll/back off.
      if (e.status != 404) throw e;
      emit(
          "MARKET_UNAVAILABLE",
          mapper.valueToTree(
              Map.of("slug", slug, "condition", condition, "url", e.url, "status", e.status)));
    }
  }

  private void metadata(JsonNode row) throws Exception {
    if (!row.path("active").asBoolean(false)
        || row.path("closed").asBoolean(true)
        || (row.path("negRisk").asBoolean(false) && !externalPaper)) return;
    boolean negativeRisk = row.path("negRisk").asBoolean(false);
    if (negativeRisk) {
      JsonNode labels = row.path("outcomes");
      if (labels.isTextual()) labels = mapper.readTree(labels.asText());
      if (labels.size() != 2
          || !labels.get(0).asText().equalsIgnoreCase("Yes")
          || !labels.get(1).asText().equalsIgnoreCase("No"))
        throw new IllegalArgumentException("Unknown negative-risk outcome slots");
    }
    JsonNode idSource = row;
    // Gamma's unversioned legacy read schema is recognizable without selecting a signing protocol.
    if (!row.hasNonNull("version")
        && row.hasNonNull("clobTokenIds")
        && !row.hasNonNull("positionIds")) {
      var copy = row.deepCopy();
      ((com.fasterxml.jackson.databind.node.ObjectNode) copy).put("version", "v1");
      idSource = copy;
    }
    List<String> ids = MarketAssetIds.parse(idSource);
    if (ids.size() != 2 || ids.get(0).equals(ids.get(1))) return;
    String condition = row.path("conditionId").asText();
    long end = Instant.parse(row.path("endDate").asText()).toEpochMilli();
    String slug = row.path("slug").asText();
    if (end <= clock.millis()) return; // Expired discovery rows need no tradable CLOB book.
    int duration = slug.contains("updown-5m-") ? 300 : slug.contains("updown-15m-") ? 900 : 3600;
    long start = end - duration * 1000L;
    if (externalPaper && !slug.contains("updown-") && !slug.contains("up-or-down-"))
      start = Instant.parse(row.path("startDate").asText()).toEpochMilli();
    JsonNode book = get("https://clob.polymarket.com/book?token_id=" + ids.get(0));
    if (!book.path("market").asText().equals(condition)
        || book.path("neg_risk").asBoolean() != negativeRisk)
      throw new IllegalArgumentException("Book identity/risk mismatch");
    JsonNode otherBook = get("https://clob.polymarket.com/book?token_id=" + ids.get(1));
    if (!book.path("asset_id").asText().equals(ids.get(0))
        || !otherBook.path("asset_id").asText().equals(ids.get(1))
        || !otherBook.path("market").asText().equals(condition)
        || otherBook.path("neg_risk").asBoolean() != negativeRisk)
      throw new IllegalArgumentException("Binary outcome membership mismatch");
    JsonNode fee = get("https://clob.polymarket.com/clob-markets/" + condition);
    var parameters = ClobMarketParameters.parse(fee, condition, Set.copyOf(ids), negativeRisk);
    BigDecimal rate = parameters.fees().rate();
    int exponent = parameters.fees().exponent();
    String evidence = "https://gamma-api.polymarket.com/markets?slug=" + slug;
    var m =
        new ResearchMarket(
            condition,
            ids.get(0),
            ids.get(1),
            start,
            end,
            new BigDecimal(book.path("tick_size").asText())
                .max(new BigDecimal(otherBook.path("tick_size").asText()))
                .max(parameters.tick()),
            new BigDecimal(book.path("min_order_size").asText())
                .max(new BigDecimal(otherBook.path("min_order_size").asText()))
                .max(parameters.minimum()),
            rate,
            exponent,
            row.path("acceptingOrders").asBoolean(false) && parameters.accepting(),
            clock.millis(),
            evidence,
            negativeRisk);
    journal.record("METADATA_EVIDENCE", null, Map.of("market", row, "book", book, "fee", fee));
    markets.put(condition, m);
    emit("META", mapper.valueToTree(m));
  }

  static long retryDeadline(String header, long now) {
    long floor = Math.addExact(now, 60000);
    try {
      return Math.max(
          floor, Math.addExact(now, Math.multiplyExact(Long.parseLong(header.trim()), 1000)));
    } catch (RuntimeException ignored) {
      try {
        return Math.max(
            floor,
            java.time.ZonedDateTime.parse(
                    header, java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME)
                .toInstant()
                .toEpochMilli());
      } catch (RuntimeException invalid) {
        return floor;
      }
    }
  }

  static final class PublicApiFailure extends IllegalStateException {
    final int status;
    final String url;

    PublicApiFailure(int status, String url) {
      super("Public API HTTP " + status + " at " + url);
      this.status = status;
      this.url = url;
    }
  }

  private JsonNode get(String url) throws Exception {
    var response =
        http.send(
            HttpRequest.newBuilder(URI.create(url))
                .GET()
                .timeout(Duration.ofSeconds(4))
                .header("Accept", "application/json")
                .build(),
            HttpResponse.BodyHandlers.ofString());
    if (response.statusCode() == 429) {
      retryAfter =
          retryDeadline(response.headers().firstValue("Retry-After").orElse(""), clock.millis());
      throw new IllegalStateException("Public API rate limit");
    }
    if (response.statusCode() != 200) throw new PublicApiFailure(response.statusCode(), url);
    return mapper.readTree(response.body());
  }
}
