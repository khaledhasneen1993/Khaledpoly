package com.polybot.hft.polymarket.ws;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.config.HftProperties;
import com.polybot.hft.events.HftEventPublisher;
import com.polybot.hft.events.HftEventTypes;
import com.polybot.hft.events.HftEventsProperties;
import com.polybot.hft.events.payload.MarketTopOfBookEvent;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.time.Clock;
import java.time.Instant;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;
import lombok.Getter;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Component
@Slf4j
@RequiredArgsConstructor
public class ClobMarketWebSocketClient {

  private static final long HEARTBEAT_LOG_INTERVAL_SECONDS = 15L;
  private static final long FRESH_TOB_LOG_THRESHOLD_MILLIS = 5_000L;

  private final @NonNull HftProperties properties;
  private final @NonNull HttpClient httpClient;
  private final @NonNull ObjectMapper objectMapper;
  private final @NonNull Clock clock;
  private final @NonNull HftEventsProperties eventsProperties;
  private final @NonNull HftEventPublisher events;

  @org.springframework.beans.factory.annotation.Autowired
  private com.polybot.hft.paper.PaperJournal journal;

  private final java.util.List<java.util.function.BiConsumer<String, JsonNode>> tapeListeners =
      new CopyOnWriteArrayList<>();

  public void onTape(java.util.function.BiConsumer<String, JsonNode> listener) {
    tapeListeners.add(listener);
  }

  private final java.util.List<java.util.function.BiConsumer<String, JsonNode>> frameListeners =
      new CopyOnWriteArrayList<>();

  /** Atomic research input; legacy onTape consumers still receive individual observations. */
  public void onFrame(java.util.function.BiConsumer<String, JsonNode> listener) {
    frameListeners.add(listener);
  }

  private record FrameEvent(String kind, Map<String, Object> data) {}

  private java.util.List<FrameEvent> frameEvents;
  private long frameSequence;
  private long frameDecodeMs = -1;

  private void tape(String kind, Map<String, Object> data) {
    if (frameEvents != null) {
      frameEvents.add(new FrameEvent(kind, data));
      return;
    }
    JsonNode node = objectMapper.valueToTree(data);
    for (var listener : frameListeners) listener.accept(kind, node);
    dispatchTape(kind, data);
  }

  private void dispatchTape(String kind, Map<String, Object> data) {
    JsonNode node = objectMapper.valueToTree(data);
    for (var listener : tapeListeners) listener.accept(kind, node);
  }

  private void gap(String reason) {
    tape("GAP", Map.of("reason", reason));
  }

  private void depthTape(String token) {
    var data = new HashMap<String, Object>(depthByAssetId.get(token).depth());
    data.put("token", token);
    data.put("sourceMs", lastSourceByAsset.get(token));
    tape("BOOK", data);
  }

  private final Map<String, TopOfBook> topOfBookByAssetId = new ConcurrentHashMap<>();
  private final Map<String, Long> lastSourceByAsset = new ConcurrentHashMap<>();
  private final Set<String> invalidatedAssets = ConcurrentHashMap.newKeySet();

  private boolean needsResnapshot() {
    return !invalidatedAssets.isEmpty();
  }

  private void invalidateAllBooks() {
    invalidatedAssets.addAll(subscribedAssetIds);
    invalidatedAssets.addAll(depthByAssetId.keySet());
    topOfBookByAssetId.clear();
    depthByAssetId.clear();
  }

  private final Map<String, LocalOrderBook> depthByAssetId = new ConcurrentHashMap<>();
  private final Map<String, BigDecimal> ticksByAssetId = new ConcurrentHashMap<>();

  public Optional<BigDecimal> observedTickSize(String token) {
    return Optional.ofNullable(ticksByAssetId.get(token));
  }

  private final Set<String> subscribedAssetIds = ConcurrentHashMap.newKeySet();
  private final Map<String, AtomicLong> lastTobEventAtMillisByAssetId = new ConcurrentHashMap<>();

  private final AtomicLong messagesReceived = new AtomicLong(0);
  private final AtomicLong bookMessages = new AtomicLong(0);
  private final AtomicLong priceChangeMessages = new AtomicLong(0);
  private final AtomicLong lastTradeMessages = new AtomicLong(0);
  private final AtomicLong lastMessageAtMillis = new AtomicLong(0);
  private final AtomicLong lastIngressNanos = new AtomicLong(0);
  private final AtomicLong lastReconnectAttemptAtMillis = new AtomicLong(0);
  private final AtomicBoolean maintenanceScheduled = new AtomicBoolean(false);

  private final ScheduledExecutorService pingExecutor =
      Executors.newSingleThreadScheduledExecutor(
          r -> {
            Thread t = new Thread(r, "clob-ws-ping");
            t.setDaemon(true);
            return t;
          });

  private final Object decodeLock = new Object();
  private final java.util.concurrent.atomic.AtomicReference<Object> reconnectTicket =
      new java.util.concurrent.atomic.AtomicReference<>();
  private final AtomicLong maxIngressCallbackMicros = new AtomicLong();
  private final MarketFrameQueue frames = new MarketFrameQueue(512, 8L * 1024 * 1024);
  private volatile WebSocket blockedSocket;
  private volatile HeartbeatProbe heartbeat = new HeartbeatProbe();

  private void enqueueFrame(WebSocket source, String message, long receivedMs, long receivedNanos) {
    if (stopping || source != webSocket || source == blockedSocket) return;
    lastIngressNanos.set(receivedNanos);
    lastMessageAtMillis.set(System.currentTimeMillis());
    if (frames.offer(
        2L * message.length(),
        () -> {
          synchronized (decodeLock) {
            if (source == webSocket && source != blockedSocket) {
              try {
                handleMessage(message, receivedMs, receivedNanos);
              } catch (RuntimeException failure) {
                blockSocket(source, receivedMs, "decoder_failure");
                throw failure;
              }
            }
          }
        })) return;
    overflowSocket(source, receivedMs);
  }

  private void overflowSocket(WebSocket source, long receivedMs) {
    blockSocket(source, receivedMs, "decoder_overflow");
  }

  private void blockSocket(WebSocket source, long receivedMs, String reason) {
    if (source != webSocket || source == blockedSocket) return;
    blockedSocket = source;
    log.warn("Market decoder blocked pending resnapshot (reason={})", reason);
    pingExecutor.execute(
        () -> {
          synchronized (decodeLock) {
            if (source != webSocket || source != blockedSocket) return;
            invalidateAllBooks();
            tape(
                "GAP",
                Map.of(
                    "reason",
                    reason,
                    "callbackReceivedMs",
                    receivedMs,
                    "queuedFrames",
                    frames.pendingFrames(),
                    "queuedBytes",
                    frames.pendingBytes()));
          }
        });
  }

  public void stopAndDrainFrames() {
    stopping = true;
    frames.close();
  }

  private volatile boolean stopping;
  private volatile WebSocket webSocket;
  @Getter private volatile boolean started = false;

  private static URI buildMarketWsUri(String baseWsUrl) {
    String base =
        baseWsUrl.endsWith("/") ? baseWsUrl.substring(0, baseWsUrl.length() - 1) : baseWsUrl;
    return URI.create(base + "/ws/market");
  }

  private static BigDecimal extractBestPrice(JsonNode levels, boolean bestIsMax) {
    if (levels == null || !levels.isArray()) {
      return null;
    }
    BigDecimal best = null;
    for (JsonNode level : levels) {
      BigDecimal p = parseDecimal(level.path("price").asText(null));
      if (p == null) {
        continue;
      }
      if (best == null) {
        best = p;
      } else if (bestIsMax && p.compareTo(best) > 0) {
        best = p;
      } else if (!bestIsMax && p.compareTo(best) < 0) {
        best = p;
      }
    }
    return best;
  }

  private static TopLevel extractBestLevel(JsonNode levels, boolean bestIsMax) {
    if (levels == null || !levels.isArray()) {
      return null;
    }
    BigDecimal bestPrice = null;
    BigDecimal bestSize = null;
    for (JsonNode level : levels) {
      BigDecimal price = parseDecimal(level.path("price").asText(null));
      if (price == null) {
        continue;
      }
      BigDecimal size = parseDecimal(level.path("size").asText(null));
      if (bestPrice == null) {
        bestPrice = price;
        bestSize = size;
        continue;
      }
      int cmp = price.compareTo(bestPrice);
      boolean better = bestIsMax ? (cmp > 0) : (cmp < 0);
      if (better) {
        bestPrice = price;
        bestSize = size;
      }
    }
    if (bestPrice == null) {
      return null;
    }
    return new TopLevel(bestPrice, bestSize);
  }

  private static BigDecimal parseDecimal(String s) {
    if (s == null || s.isBlank()) {
      return null;
    }
    return new BigDecimal(s);
  }

  private static String sampleAssetSuffixes(List<String> assetIds, int max) {
    if (assetIds == null || assetIds.isEmpty() || max <= 0) {
      return "[]";
    }
    return assetIds.stream()
        .limit(max)
        .map(ClobMarketWebSocketClient::suffix)
        .collect(Collectors.joining(", ", "[", assetIds.size() > max ? ", ...]" : "]"));
  }

  private static String suffix(String tokenId) {
    if (tokenId == null) {
      return "null";
    }
    String t = tokenId.trim();
    if (t.length() <= 6) {
      return t;
    }
    return "..." + t.substring(t.length() - 6);
  }

  private static List<String> sanitize(List<String> assetIds) {
    if (assetIds == null || assetIds.isEmpty()) {
      return List.of();
    }
    return assetIds.stream()
        .filter(s -> s != null && !s.isBlank())
        .map(String::trim)
        .distinct()
        .collect(Collectors.toList());
  }

  public Optional<TopOfBook> getTopOfBook(String assetId) {
    if (webSocket != null && webSocket == blockedSocket) return Optional.empty();
    return depthByAssetId.containsKey(assetId)
        ? Optional.ofNullable(topOfBookByAssetId.get(assetId))
        : Optional.empty();
  }

  public int subscribedAssetCount() {
    return subscribedAssetIds.size();
  }

  public int topOfBookCount() {
    return topOfBookByAssetId.size();
  }

  @PostConstruct
  void startIfEnabled() {
    HftProperties.Polymarket polymarket = properties.polymarket();
    if (!polymarket.marketWsEnabled()) {
      return;
    }
    maybeLoadCacheFromDisk();
    List<String> assets = polymarket.marketAssetIds();
    if (assets != null && !assets.isEmpty()) {
      subscribeAssets(assets);
      return;
    }
    if (!subscribedAssetIds.isEmpty()) {
      log.info(
          "Market WS enabled; warm-started with {} cached subscriptions.",
          subscribedAssetIds.size());
      return;
    }
    log.info("Market WS enabled; waiting for market asset subscriptions.");
  }

  public void subscribeAssets(List<String> assetIds) {
    if (!properties.polymarket().marketWsEnabled()) {
      return;
    }
    List<String> sanitized = sanitize(assetIds);
    if (sanitized.isEmpty()) {
      return;
    }

    synchronized (this) {
      boolean changed = subscribedAssetIds.addAll(sanitized);
      if (!started) {
        connectLocked();
        return;
      }
      if (changed) {
        reconnectLocked();
      }
    }
  }

  /**
   * Replace the current subscription set (prunes old assets).
   *
   * <p>Important for WS decision-time coverage: add-only subscriptions accumulate expired markets
   * over time, which bloats caches and makes "fresh TOB" effectively unattainable for the active
   * universe.
   */
  public void setSubscribedAssets(List<String> assetIds) {
    if (!properties.polymarket().marketWsEnabled()) {
      return;
    }
    List<String> sanitized = sanitize(assetIds);
    if (sanitized.isEmpty()) {
      return;
    }

    Set<String> desired = new HashSet<>(sanitized);
    synchronized (this) {
      if (subscribedAssetIds.equals(desired)) {
        return;
      }

      subscribedAssetIds.clear();
      subscribedAssetIds.addAll(desired);

      // Prune stale caches so we don't persist/heartbeat thousands of dead markets.
      topOfBookByAssetId.keySet().retainAll(desired);
      lastTobEventAtMillisByAssetId.keySet().retainAll(desired);

      if (!started) {
        connectLocked();
        return;
      }
      reconnectLocked();
    }
  }

  private void reconnectLocked() {
    // Callers may own the simulator monitor. Never wait for a decoder that calls that simulator.
    Object ticket = new Object();
    if (stopping || !reconnectTicket.compareAndSet(null, ticket)) return;
    pingExecutor.execute(
        () -> {
          try {

            WebSocket ws;
            synchronized (decodeLock) {
              ws = this.webSocket;
              this.webSocket = null;
              started = false;
              gap("reconnect");
              lastMessageAtMillis.set(0);
              lastTobEventAtMillisByAssetId.clear();
              topOfBookByAssetId.clear();
              depthByAssetId.clear();
              invalidatedAssets.clear();
              lastSourceByAsset.clear();
              ticksByAssetId.clear();
              blockedSocket = null;
            }
            if (ws != null) {
              try {
                ws.sendClose(WebSocket.NORMAL_CLOSURE, "resubscribe")
                    .orTimeout(2, TimeUnit.SECONDS)
                    .join();
              } catch (Exception ignored) {
              }
            }
            synchronized (this) {
              try {
                if (!stopping) connectLocked();
              } finally {
                reconnectTicket.compareAndSet(ticket, null);
              }
            }
          } finally {
            reconnectTicket.compareAndSet(ticket, null);
          }
        });
  }

  private void connectLocked() {
    if (stopping || started) {
      return;
    }
    started = true;

    URI wsUri = buildMarketWsUri(properties.polymarket().clobWsUrl());
    log.info("Connecting to CLOB market websocket: {}", wsUri);

    CompletableFuture<WebSocket> cf =
        httpClient.newWebSocketBuilder().buildAsync(wsUri, new Listener());
    try {
      this.webSocket = cf.orTimeout(10, TimeUnit.SECONDS).join();
    } catch (RuntimeException e) {
      started = false;
      throw e;
    }

    if (maintenanceScheduled.compareAndSet(false, true)) {
      pingExecutor.scheduleAtFixedRate(this::sendHeartbeat, 10, 10, TimeUnit.SECONDS);

      pingExecutor.scheduleAtFixedRate(
          this::logHeartbeat,
          HEARTBEAT_LOG_INTERVAL_SECONDS,
          HEARTBEAT_LOG_INTERVAL_SECONDS,
          TimeUnit.SECONDS);
      pingExecutor.scheduleAtFixedRate(this::maintainConnectionSafely, 5, 5, TimeUnit.SECONDS);

      long snapshotMillis = eventsProperties.marketWsSnapshotPublishMillis();
      if (snapshotMillis > 0) {
        pingExecutor.scheduleAtFixedRate(
            this::republishSnapshotsSafely, snapshotMillis, snapshotMillis, TimeUnit.MILLISECONDS);
      }

      long flushMillis = properties.polymarket().marketWsCacheFlushMillis();
      if (flushMillis > 0 && isCachePersistenceEnabled()) {
        pingExecutor.scheduleAtFixedRate(
            this::flushCacheSafely, flushMillis, flushMillis, TimeUnit.MILLISECONDS);
      }
    }
  }

  private long ingressAgeMs() {
    long ingress = lastIngressNanos.get();
    return ingress == 0 ? -1 : Math.max(0, (System.nanoTime() - ingress) / 1_000_000);
  }

  private void sendHeartbeat() {
    WebSocket ws = webSocket;
    if (stopping || ws == null) return;
    HeartbeatProbe probe = heartbeat;
    probe.ping(clock.millis(), System.nanoTime(), () -> ws.sendText("PING", true));
    if (journal != null && journal.enabled()) {
      var data = new HashMap<String, Object>(probe.snapshot());
      data.put("lastIngressAgeMs", ingressAgeMs());
      data.put("queuedFrames", frames.pendingFrames());
      data.put("queuedBytes", frames.pendingBytes());
      data.put(
          "lastActivityAgeMs", Math.max(0, System.currentTimeMillis() - lastMessageAtMillis.get()));
      long gcCount = 0, gcMillis = 0;
      for (var gc : java.lang.management.ManagementFactory.getGarbageCollectorMXBeans()) {
        gcCount += Math.max(0, gc.getCollectionCount());
        gcMillis += Math.max(0, gc.getCollectionTime());
      }
      data.put("gcCount", gcCount);
      data.put("gcMillis", gcMillis);
      data.put(
          "heapUsedBytes", Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory());
      journal.record("WS_HEARTBEAT", null, data);
    }
  }

  @PreDestroy
  void shutdown() {
    stopAndDrainFrames();
    flushCacheSafely();
    WebSocket ws = this.webSocket;
    if (ws != null) {
      try {
        ws.sendClose(WebSocket.NORMAL_CLOSURE, "shutdown").orTimeout(2, TimeUnit.SECONDS).join();
      } catch (Exception ignored) {
      }
    }
    pingExecutor.shutdownNow();
  }

  private String buildSubscribeMessage(List<String> assetIds) {
    try {
      return objectMapper.writeValueAsString(
          Map.of("assets_ids", assetIds, "type", "market", "custom_feature_enabled", true));
    } catch (Exception e) {
      throw new IllegalStateException("Failed to build market ws subscribe message", e);
    }
  }

  private void sendSubscribeLocked() {
    WebSocket ws = this.webSocket;
    if (ws == null) {
      return;
    }
    List<String> snapshot = subscribedAssetIds.stream().sorted().toList();
    if (snapshot.isEmpty()) {
      return;
    }
    String subscription = buildSubscribeMessage(snapshot);
    if (journal != null) journal.record("PUBLIC_SUBSCRIPTION", null, Map.of("text", subscription));
    ws.sendText(subscription, true);
    log.info(
        "Subscribed to {} market assets via WS (e.g. {})",
        snapshot.size(),
        sampleAssetSuffixes(snapshot, 4));
  }

  private void handleMessage(String message) {
    handleMessage(message, clock.millis(), System.nanoTime());
  }

  private long pipelineWindowNanos = System.nanoTime();
  private long pipelineFrames, maxProcessingMicros, maxRawAppendMicros, maxQueueWaitMicros;

  private final Object pipelineLock = new Object();

  private void pipelineTiming(long receivedNanos, long startedNanos, long rawDoneNanos) {
    synchronized (pipelineLock) {
      if (journal == null || !journal.enabled()) return;
      long now = System.nanoTime();
      pipelineFrames++;
      maxProcessingMicros = Math.max(maxProcessingMicros, (now - startedNanos) / 1000);
      maxRawAppendMicros = Math.max(maxRawAppendMicros, (rawDoneNanos - startedNanos) / 1000);
      maxQueueWaitMicros = Math.max(maxQueueWaitMicros, (startedNanos - receivedNanos) / 1000);
      if (now - pipelineWindowNanos < 1_000_000_000L) return;
      journal.record(
          "WS_PIPELINE",
          null,
          Map.of(
              "frames",
              pipelineFrames,
              "intervalMicros",
              (now - pipelineWindowNanos) / 1000,
              "maxDecoderProcessingMicros",
              maxProcessingMicros,
              "maxIngressCallbackMicros",
              maxIngressCallbackMicros.get(),
              "maxRawAppendMicros",
              maxRawAppendMicros,
              "maxQueueWaitMicros",
              maxQueueWaitMicros,
              "queuedFrames",
              frames.pendingFrames(),
              "queuedBytes",
              frames.pendingBytes(),
              "journal",
              journal.stats()));
      pipelineFrames = maxProcessingMicros = maxRawAppendMicros = maxQueueWaitMicros = 0;
      pipelineWindowNanos = System.nanoTime();
    }
  }

  private void handleMessage(String message, long receivedMs, long receivedNanos) {
    long startedNanos = System.nanoTime();
    if ("PONG".equalsIgnoreCase(message) || "PING".equalsIgnoreCase(message)) {
      lastMessageAtMillis.set(System.currentTimeMillis());
      return;
    }
    messagesReceived.incrementAndGet();
    lastMessageAtMillis.set(System.currentTimeMillis());
    long rawDoneNanos = startedNanos;
    long frameId = ++frameSequence;
    frameEvents = new java.util.ArrayList<>();
    try {
      if (journal != null)
        journal.record(
            "RAW_MARKET",
            null,
            Map.of("text", message, "callbackReceivedMs", receivedMs, "frameId", frameId));
      rawDoneNanos = System.nanoTime();
      frameDecodeMs = clock.millis();
      JsonNode node = objectMapper.readTree(message);
      handleMessageNode(node, receivedMs);
    } catch (Exception e) {
      frameEvents.clear();
      invalidateAllBooks();
      gap("invalid_message");
      log.warn("Invalid market message; books invalidated: {}", e.getMessage());
    } finally {
      var completed = frameEvents;
      frameEvents = null;
      // One availability clock and one strategy transition for the entire socket message.
      // No listener can observe a new first leg with an old second leg from that same message.
      JsonNode frame =
          objectMapper.valueToTree(
              Map.of(
                  "frameId",
                  frameId,
                  "decodedMs",
                  frameDecodeMs >= 0 ? frameDecodeMs : clock.millis(),
                  "events",
                  completed));
      frameDecodeMs = -1;
      for (var listener : frameListeners) listener.accept("FRAME", frame);
      for (var event : completed) dispatchTape(event.kind(), event.data());
      pipelineTiming(receivedNanos, startedNanos, rawDoneNanos);
    }
  }

  private void handleMessageNode(JsonNode node, long receivedMs) {
    if (node == null || node.isNull()) {
      return;
    }
    if (node.isArray()) {
      for (JsonNode n : node) {
        handleMessageNode(n, receivedMs);
      }
      return;
    }

    String eventType = node.path("event_type").asText("");
    if ((eventType.equals("book") || eventType.equals("price_change")) && !sourceFresh(node)) {
      long stamp = node.path("timestamp").asLong(-1);
      if (stamp > 0 && stamp < 100000000000L) stamp *= 1000;
      var tokens = com.polybot.hft.paper.DataGap.messageTokens(node);
      // An older observation cannot invalidate a newer accepted snapshot.
      tokens.removeIf(token -> stampForComparison(node) >= 0
          && stampForComparison(node) < lastSourceByAsset.getOrDefault(token, -1L));
      if (!com.polybot.hft.paper.DataGap.messageTokens(node).isEmpty() && tokens.isEmpty()) return;
      if (tokens.isEmpty()) invalidateAllBooks();
      else for (String token : tokens) {
        invalidatedAssets.add(token);
        topOfBookByAssetId.remove(token);
        depthByAssetId.remove(token);
      }
      long observedMs = frameDecodeMs >= 0 ? frameDecodeMs : clock.millis();
      tape(
          "GAP",
          Map.of(
              "reason",
              "stale_source",
              "tokens", tokens,
              "sourceMs",
              stamp,
              "callbackReceivedMs",
              receivedMs,
              "observedMs",
              observedMs,
              "callbackSourceAgeMs",
              receivedMs - stamp,
              "processingAgeMs",
              observedMs - receivedMs));
      return;
    }
    switch (eventType) {
      case "book" -> {
        bookMessages.incrementAndGet();
        handleBook(node);
      }
      case "price_change" -> {
        priceChangeMessages.incrementAndGet();
        handlePriceChange(node);
      }
      case "tick_size_change" -> {
        String asset = node.path("asset_id").asText();
        BigDecimal tick = parseDecimal(node.path("new_tick_size").asText());
        if (tick != null && tick.signum() > 0) {
          ticksByAssetId.put(asset, tick);
          long stamp = node.path("timestamp").asLong(-1);
          if (stamp > 0 && stamp < 100000000000L) stamp *= 1000;
          tape("TICK_SIZE", Map.of("token", asset, "tick", tick, "sourceMs", stamp));
        }
      }
      case "last_trade_price" -> {
        lastTradeMessages.incrementAndGet();
        handleLastTradePrice(node);
      }
      default -> {}
    }
  }

  private boolean acceptSource(String asset, JsonNode node) {
    long stamp = Long.parseLong(node.path("timestamp").asText());
    if (stamp < 100000000000L) stamp = Math.multiplyExact(stamp, 1000);
    Long previous = lastSourceByAsset.get(asset);
    if (previous != null && stamp < previous) return false;
    lastSourceByAsset.put(asset, stamp);
    return true;
  }

  private long stampForComparison(JsonNode node) {
    long stamp = node.path("timestamp").asLong(-1);
    return stamp > 0 && stamp < 100000000000L ? stamp * 1000 : stamp;
  }

  private boolean sourceFresh(JsonNode node) {
    try {
      long stamp = Long.parseLong(node.path("timestamp").asText());
      if (stamp < 100000000000L) stamp = Math.multiplyExact(stamp, 1000);
      long age = (frameDecodeMs >= 0 ? frameDecodeMs : clock.millis()) - stamp;
      return age >= 0 && age <= 2000;
    } catch (RuntimeException e) {
      return false;
    }
  }

  private void maintainConnectionSafely() {
    try {
      maintainConnection();
    } catch (Exception e) {
      log.debug("Market WS maintenance failed: {}", e.toString());
    }
  }

  private void maintainConnection() {
    if (stopping || !properties.polymarket().marketWsEnabled()) {
      return;
    }
    if (subscribedAssetIds.isEmpty()) {
      return;
    }

    long staleTimeoutMillis = properties.polymarket().marketWsStaleTimeoutMillis();
    long reconnectBackoffMillis = properties.polymarket().marketWsReconnectBackoffMillis();
    long now = System.currentTimeMillis();

    boolean disconnected =
        !started || webSocket == null || webSocket == blockedSocket || needsResnapshot();
    long lastAt = lastMessageAtMillis.get();
    boolean stale = staleTimeoutMillis > 0 && lastAt > 0 && (now - lastAt) > staleTimeoutMillis;
    if (!disconnected && !stale) {
      return;
    }

    long prevAttempt = lastReconnectAttemptAtMillis.get();
    if (reconnectBackoffMillis > 0
        && prevAttempt > 0
        && now - prevAttempt < reconnectBackoffMillis) {
      return;
    }
    lastReconnectAttemptAtMillis.set(now);

    String reason = disconnected ? "disconnected" : "stale";
    long lastAgo = lastAt <= 0 ? -1 : now - lastAt;
    log.warn(
        "Market WS reconnecting (reason={}, subscribed={}, tobKnown={}, lastMsgAgoMs={})",
        reason,
        subscribedAssetIds.size(),
        topOfBookByAssetId.size(),
        lastAgo);

    synchronized (this) {
      if (subscribedAssetIds.isEmpty()) {
        return;
      }
      reconnectLocked();
    }
  }

  private void logHeartbeat() {
    if (!started) {
      return;
    }
    long now = System.currentTimeMillis();
    long lastAt = lastMessageAtMillis.get();
    String lastAgo = lastAt <= 0 ? "never" : (now - lastAt) + "ms ago";

    int subscribed = subscribedAssetIds.size();
    int known = topOfBookByAssetId.size();
    int fresh = 0;
    for (String assetId : subscribedAssetIds) {
      TopOfBook tob = topOfBookByAssetId.get(assetId);
      if (tob == null || tob.updatedAt() == null) {
        continue;
      }
      if (now - tob.updatedAt().toEpochMilli() <= FRESH_TOB_LOG_THRESHOLD_MILLIS) {
        fresh++;
      }
    }
    log.info(
        "Market WS heartbeat subscribed={} tobKnown={} tobFresh({}ms)={} msgs={} book={}"
            + " priceChange={} lastTrade={} lastMsg={}",
        subscribed,
        known,
        FRESH_TOB_LOG_THRESHOLD_MILLIS,
        fresh,
        messagesReceived.get(),
        bookMessages.get(),
        priceChangeMessages.get(),
        lastTradeMessages.get(),
        lastAgo);
  }

  private void republishSnapshotsSafely() {
    try {
      republishSnapshots();
    } catch (Exception e) {
      log.debug("Market WS snapshot republish failed: {}", e.toString());
    }
  }

  private void republishSnapshots() {
    if (!started) {
      return;
    }
    if (!events.isEnabled()) {
      return;
    }
    if (subscribedAssetIds.isEmpty() || topOfBookByAssetId.isEmpty()) {
      return;
    }

    long staleTimeoutMillis = properties.polymarket().marketWsStaleTimeoutMillis();
    long nowMillis = System.currentTimeMillis();
    long lastAt = lastMessageAtMillis.get();
    boolean stale =
        staleTimeoutMillis > 0 && lastAt > 0 && (nowMillis - lastAt) > staleTimeoutMillis;
    if (stale) {
      return;
    }

    Instant now = Instant.now(clock);
    for (String assetId : subscribedAssetIds) {
      TopOfBook tob = topOfBookByAssetId.get(assetId);
      if (tob == null || tob.bestBid() == null || tob.bestAsk() == null) {
        continue;
      }

      TopOfBook snapshot =
          new TopOfBook(
              tob.bestBid(),
              tob.bestAsk(),
              tob.bestBidSize(),
              tob.bestAskSize(),
              tob.lastTradePrice(),
              tob.updatedAt(),
              tob.lastTradeAt());
      topOfBookByAssetId.put(assetId, snapshot);
      maybePublishTopOfBook(assetId, snapshot);
    }
  }

  private void handleBook(JsonNode node) {
    String assetId = node.path("asset_id").asText(null);
    if (assetId == null) {
      return;
    }
    if (!acceptSource(assetId, node)) return;
    JsonNode bidsNode = node.has("bids") ? node.get("bids") : node.get("buys");
    JsonNode asksNode = node.has("asks") ? node.get("asks") : node.get("sells");

    LocalOrderBook depth = new LocalOrderBook();
    depth.snapshot(bidsNode, asksNode);
    depthByAssetId.put(assetId, depth);
    // Only a validated full snapshot restores confidence, never a best-price hint or lone delta.
    invalidatedAssets.remove(assetId);
    LocalOrderBook.Best best = depth.best();
    BigDecimal bestBid = best.bid(),
        bestBidSize = best.bidSize(),
        bestAsk = best.ask(),
        bestAskSize = best.askSize();
    BigDecimal lastTradePrice = parseDecimal(node.path("last_trade_price").asText(null));

    Instant now = Instant.now(clock);
    TopOfBook tob =
        topOfBookByAssetId.compute(
            assetId,
            (k, prev) -> {
              BigDecimal prevLast = prev == null ? null : prev.lastTradePrice();
              Instant prevTradeAt = prev == null ? null : prev.lastTradeAt();

              BigDecimal nextLast = lastTradePrice != null ? lastTradePrice : prevLast;
              Instant nextTradeAt = prevTradeAt;
              if (nextLast != null
                  && (prevLast == null
                      || (lastTradePrice != null
                          && prevLast != null
                          && lastTradePrice.compareTo(prevLast) != 0))) {
                nextTradeAt = now;
              }
              BigDecimal nextBidSize =
                  bestBidSize != null ? bestBidSize : (prev == null ? null : prev.bestBidSize());
              BigDecimal nextAskSize =
                  bestAskSize != null ? bestAskSize : (prev == null ? null : prev.bestAskSize());
              return new TopOfBook(
                  bestBid, bestAsk, nextBidSize, nextAskSize, nextLast, now, nextTradeAt);
            });
    depthTape(assetId);
    maybePublishTopOfBook(assetId, tob);
  }

  private void handlePriceChange(JsonNode node) {
    JsonNode changes = node.path("price_changes");
    if (!changes.isArray()) {
      return;
    }
    Instant now = Instant.now(clock);
    var batches =
        new java.util.LinkedHashMap<String, com.fasterxml.jackson.databind.node.ArrayNode>();
    for (JsonNode change : changes)
      batches
          .computeIfAbsent(change.path("asset_id").asText(), k -> objectMapper.createArrayNode())
          .add(change);
    for (var batch : batches.entrySet()) {
      String assetId = batch.getKey();
      if (assetId == null) {
        continue;
      }
      if (!acceptSource(assetId, node)) continue;
      LocalOrderBook depth = depthByAssetId.get(assetId);
      if (depth == null) {
        topOfBookByAssetId.remove(assetId);
        continue;
      }
      try {
        depth.changes(batch.getValue());
      } catch (RuntimeException e) {
        depthByAssetId.remove(assetId);
        topOfBookByAssetId.remove(assetId);
        invalidatedAssets.add(assetId);
        tape(
            "GAP",
            Map.of(
                "reason",
                "invalid_depth",
                "token",
                assetId,
                "sourceMs",
                lastSourceByAsset.get(assetId),
                "detail",
                e.getMessage()));
        continue;
      }
      LocalOrderBook.Best best = depth.best();
      BigDecimal bestBid = best.bid(),
          bestAsk = best.ask(),
          bestBidSize = best.bidSize(),
          bestAskSize = best.askSize();

      TopOfBook tob =
          topOfBookByAssetId.compute(
              assetId,
              (k, prev) ->
                  new TopOfBook(
                      bestBid,
                      bestAsk,
                      bestBidSize,
                      bestAskSize,
                      prev == null ? null : prev.lastTradePrice(),
                      now,
                      prev == null ? null : prev.lastTradeAt()));
      depthTape(assetId);
      maybePublishTopOfBook(assetId, tob);
    }
  }

  private void handleLastTradePrice(JsonNode node) {
    String assetId = node.path("asset_id").asText(null);
    if (assetId == null) {
      return;
    }
    if (!sourceFresh(node)) return;
    long source = Long.parseLong(node.path("timestamp").asText());
    if (source < 100000000000L) source *= 1000;
    // Full message fingerprint, not just transaction hash (one transaction can contain many
    // prints).
    tape(
        "TRADE",
        Map.of(
            "token",
            assetId,
            "side",
            node.path("side").asText(),
            "price",
            node.path("price").asText(),
            "size",
            node.path("size").asText(),
            "sourceMs",
            source,
            "tradeId",
            node.toString()));
    BigDecimal price = parseDecimal(node.path("price").asText(null));
    Instant now = Instant.now(clock);
    TopOfBook tob =
        topOfBookByAssetId.compute(
            assetId,
            (k, prev) ->
                new TopOfBook(
                    prev == null ? null : prev.bestBid(),
                    prev == null ? null : prev.bestAsk(),
                    prev == null ? null : prev.bestBidSize(),
                    prev == null ? null : prev.bestAskSize(),
                    price,
                    prev == null ? Instant.EPOCH : prev.updatedAt(),
                    now));
    maybePublishTopOfBook(assetId, tob);
  }

  private void maybePublishTopOfBook(String assetId, TopOfBook tob) {
    if (assetId == null || assetId.isBlank() || tob == null) {
      return;
    }
    if (!events.isEnabled()) {
      return;
    }

    long minIntervalMillis = eventsProperties.marketWsTobMinIntervalMillis();
    long nowMillis =
        tob.updatedAt() != null ? tob.updatedAt().toEpochMilli() : System.currentTimeMillis();
    if (minIntervalMillis > 0) {
      AtomicLong last =
          lastTobEventAtMillisByAssetId.computeIfAbsent(assetId, k -> new AtomicLong(0L));
      while (true) {
        long prev = last.get();
        if (nowMillis - prev < minIntervalMillis) {
          return;
        }
        if (last.compareAndSet(prev, nowMillis)) {
          break;
        }
      }
    }

    events.publish(
        tob.updatedAt(),
        HftEventTypes.MARKET_WS_TOB,
        assetId,
        new MarketTopOfBookEvent(
            assetId,
            tob.bestBid(),
            tob.bestBidSize(),
            tob.bestAsk(),
            tob.bestAskSize(),
            tob.lastTradePrice(),
            tob.updatedAt(),
            tob.lastTradeAt()));
  }

  private record TopLevel(BigDecimal price, BigDecimal size) {}

  private boolean isCachePersistenceEnabled() {
    String path = properties.polymarket().marketWsCachePath();
    return path != null && !path.isBlank();
  }

  private void maybeLoadCacheFromDisk() {
    if (!isCachePersistenceEnabled()) {
      return;
    }
    String pathStr = properties.polymarket().marketWsCachePath();
    Path path;
    try {
      path = Path.of(pathStr);
    } catch (Exception e) {
      log.warn("Market WS cache path is invalid: {}", pathStr);
      return;
    }
    if (!Files.exists(path)) {
      return;
    }
    try {
      String json = Files.readString(path);
      if (json == null || json.isBlank()) {
        return;
      }
      MarketWsCacheSnapshot snapshot = objectMapper.readValue(json, MarketWsCacheSnapshot.class);
      if (snapshot == null
          || snapshot.topOfBookByAssetId() == null
          || snapshot.topOfBookByAssetId().isEmpty()) {
        return;
      }
      topOfBookByAssetId.putAll(snapshot.topOfBookByAssetId());
      log.info(
          "Loaded market WS TOB cache from {} (assets={})",
          pathStr,
          snapshot.topOfBookByAssetId().size());

      if (Boolean.TRUE.equals(eventsProperties.marketWsCachePublishOnStart())
          && events.isEnabled()) {
        for (Map.Entry<String, TopOfBook> e : snapshot.topOfBookByAssetId().entrySet()) {
          if (e == null) {
            continue;
          }
          String assetId = e.getKey();
          TopOfBook tob = e.getValue();
          if (assetId == null || assetId.isBlank() || tob == null) {
            continue;
          }
          maybePublishTopOfBook(assetId, tob);
        }
        log.info(
            "Republished {} cached market WS TOBs on startup",
            snapshot.topOfBookByAssetId().size());
      }

      // Optional warm-start: if no asset list was configured, reuse the last subscribed set to
      // connect immediately.
      if (properties.polymarket().marketAssetIds().isEmpty()
          && snapshot.subscribedAssetIds() != null
          && !snapshot.subscribedAssetIds().isEmpty()
          && subscribedAssetIds.isEmpty()) {
        setSubscribedAssets(snapshot.subscribedAssetIds());
      }
    } catch (Exception e) {
      log.warn("Failed to load market WS TOB cache from {}: {}", pathStr, e.getMessage());
    }
  }

  private void flushCacheSafely() {
    if (!isCachePersistenceEnabled()) {
      return;
    }
    try {
      flushCacheToDisk();
    } catch (Exception e) {
      log.debug("Market WS cache flush failed: {}", e.getMessage());
    }
  }

  private void flushCacheToDisk() throws Exception {
    String pathStr = properties.polymarket().marketWsCachePath();
    if (pathStr == null || pathStr.isBlank()) {
      return;
    }

    Path path = Path.of(pathStr);
    Path parent = path.getParent();
    if (parent != null) {
      Files.createDirectories(parent);
    }

    MarketWsCacheSnapshot snapshot =
        new MarketWsCacheSnapshot(
            Instant.now(clock),
            subscribedAssetIds.stream().sorted().toList(),
            new HashMap<>(topOfBookByAssetId));

    String json = objectMapper.writeValueAsString(snapshot);
    Path tmp = path.resolveSibling(path.getFileName() + ".tmp");
    Files.writeString(
        tmp,
        json,
        StandardOpenOption.CREATE,
        StandardOpenOption.TRUNCATE_EXISTING,
        StandardOpenOption.WRITE);
    try {
      Files.move(tmp, path, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    } catch (Exception e) {
      Files.move(tmp, path, StandardCopyOption.REPLACE_EXISTING);
    }
  }

  private record MarketWsCacheSnapshot(
      Instant snapshotAt,
      List<String> subscribedAssetIds,
      Map<String, TopOfBook> topOfBookByAssetId) {}

  private final class Listener implements WebSocket.Listener {
    private final StringBuilder buf = new StringBuilder(8192);

    private Listener() {}

    @Override
    public void onOpen(WebSocket webSocket) {
      log.info("CLOB market websocket opened");
      heartbeat = new HeartbeatProbe();
      lastIngressNanos.set(0);
      ClobMarketWebSocketClient.this.webSocket = webSocket;
      lastMessageAtMillis.set(System.currentTimeMillis());
      sendSubscribeLocked();
      webSocket.request(1);
    }

    @Override
    public CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
      if (stopping
          || ClobMarketWebSocketClient.this.webSocket != webSocket
          || webSocket == blockedSocket) {
        webSocket.request(1);
        return null;
      }
      long receivedMs = clock.millis(), receivedNanos = System.nanoTime();
      lastIngressNanos.set(receivedNanos);
      if ((long) buf.length() + data.length() > 4L * 1024 * 1024) {
        buf.setLength(0);
        overflowSocket(webSocket, receivedMs);
        webSocket.request(1);
        maxIngressCallbackMicros.accumulateAndGet(
            (System.nanoTime() - receivedNanos) / 1000, Math::max);
        return null;
      }
      buf.append(data);
      if (last) {
        String message = buf.toString();
        buf.setLength(0);
        if ("PONG".equalsIgnoreCase(message)) {
          // No disk IO on the receive callback; the timer/close records these counters.
          heartbeat.pong(receivedMs, receivedNanos);
          lastMessageAtMillis.set(System.currentTimeMillis());
        } else enqueueFrame(webSocket, message, receivedMs, receivedNanos);
      }
      webSocket.request(1);
      maxIngressCallbackMicros.accumulateAndGet(
          (System.nanoTime() - receivedNanos) / 1000, Math::max);
      return null;
    }

    @Override
    public CompletionStage<?> onPong(WebSocket webSocket, ByteBuffer message) {
      lastMessageAtMillis.set(System.currentTimeMillis());
      webSocket.request(1);
      return null;
    }

    @Override
    public CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
      log.warn("CLOB market websocket closed (status={}, reason={})", statusCode, reason);
      synchronized (decodeLock) {
        if (ClobMarketWebSocketClient.this.webSocket == webSocket) {
          ClobMarketWebSocketClient.this.webSocket = null;
          started = false;
          topOfBookByAssetId.clear();
          depthByAssetId.clear();
          if (!stopping) {
            var detail = new HashMap<String, Object>(heartbeat.snapshot());
            detail.put("reason", "disconnect");
            detail.put("status", statusCode);
            detail.put("detail", reason);
            detail.put("lastIngressAgeMs", ingressAgeMs());
            detail.put("queuedFrames", frames.pendingFrames());
            detail.put("queuedBytes", frames.pendingBytes());
            detail.put(
                "lastActivityAgeMs",
                Math.max(0, System.currentTimeMillis() - lastMessageAtMillis.get()));
            tape("GAP", detail);
          }
        }
      }
      return WebSocket.Listener.super.onClose(webSocket, statusCode, reason);
    }

    @Override
    public void onError(WebSocket webSocket, Throwable error) {
      log.warn("CLOB market websocket error: {}", error.toString());
      synchronized (decodeLock) {
        if (ClobMarketWebSocketClient.this.webSocket == webSocket) {
          ClobMarketWebSocketClient.this.webSocket = null;
          started = false;
          topOfBookByAssetId.clear();
          depthByAssetId.clear();
          if (!stopping) gap("socket_error");
        }
      }
    }
  }
}
