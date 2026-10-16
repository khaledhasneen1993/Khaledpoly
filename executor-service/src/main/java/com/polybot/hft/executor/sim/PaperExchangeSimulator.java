package com.polybot.hft.executor.sim;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.polybot.hft.config.HftProperties;
import com.polybot.hft.domain.OrderSide;
import com.polybot.hft.events.HftEventPublisher;
import com.polybot.hft.events.HftEventTypes;
import com.polybot.hft.executor.events.ExecutorOrderStatusEvent;
import com.polybot.hft.polymarket.api.LimitOrderRequest;
import com.polybot.hft.polymarket.api.MarketOrderRequest;
import com.polybot.hft.polymarket.api.OrderSubmissionResult;
import com.polybot.hft.polymarket.data.PolymarketPosition;
import com.polybot.hft.polymarket.gamma.PolymarketGammaClient;
import com.polybot.hft.polymarket.ws.ClobMarketWebSocketClient;
import com.polybot.hft.polymarket.ws.TopOfBook;
import jakarta.annotation.PostConstruct;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ThreadLocalRandom;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * A lightweight "paper exchange" simulator for local testing.
 *
 * <p>Goals: - Exercise the full strategy/executor lifecycle without touching real funds - Provide
 * realistic-ish order status transitions (OPEN -> PARTIAL -> FILLED/CANCELED) - Optionally publish
 * simulated polymarket.user.trade events so ClickHouse views/analysis can run
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class PaperExchangeSimulator {

  private static final String USER_TRADE_EVENT_TYPE = "polymarket.user.trade";

  private final @NonNull HftProperties hft;
  private final @NonNull ExecutorSimulationProperties sim;
  private final @NonNull ObjectMapper objectMapper;
  private final @NonNull Clock clock;
  private final @NonNull HftEventPublisher events;
  private final @NonNull ClobMarketWebSocketClient marketWs;
  private final @NonNull PolymarketGammaClient gammaClient;
  private final @NonNull com.polybot.hft.polymarket.service.MarketPolicyService marketPolicy;

  @org.springframework.beans.factory.annotation.Value("${executor.account.initial-cash:500}")
  private BigDecimal initialCash;

  @org.springframework.beans.factory.annotation.Value("${executor.account.max-order:25}")
  private BigDecimal maxOrder;

  @org.springframework.beans.factory.annotation.Value("${executor.account.max-token-exposure:25}")
  private BigDecimal maxTokenExposure;

  @org.springframework.beans.factory.annotation.Value("${executor.account.max-gross-exposure:250}")
  private BigDecimal maxGrossExposure;

  @org.springframework.beans.factory.annotation.Value("${executor.account.daily-loss:25}")
  private BigDecimal dailyLoss;

  @org.springframework.beans.factory.annotation.Value("${executor.account.drawdown:50}")
  private BigDecimal drawdown;

  @org.springframework.beans.factory.annotation.Value(
      "${executor.account.state-path:state/paper-account.json}")
  private String statePath;

  private com.polybot.hft.risk.AccountLedger ledger;
  private volatile boolean recoveryBlocked;

  public com.polybot.hft.risk.AccountLedger.State accountState() {
    return ledger.snapshot();
  }

  public BigDecimal availableCash() {
    return ledger.availableCash();
  }

  public synchronized BigDecimal equity() {
    Map<String, BigDecimal> marks = new java.util.HashMap<>();
    for (var e : ledger.snapshot().holdings().entrySet())
      if (e.getValue().shares().signum() > 0) {
        TopOfBook book =
            marketWs
                .getTopOfBook(e.getKey())
                .orElseThrow(() -> new IllegalStateException("Inventory book unavailable"));
        if (book.updatedAt() == null
            || java.time.Duration.between(book.updatedAt(), clock.instant()).toMillis() > 2000)
          throw new IllegalStateException("Inventory book stale");
        marks.put(e.getKey(), book.bestBid());
      }
    BigDecimal equity = ledger.mark(marks);
    if (ledger.snapshot().halted()) {
      for (String id : java.util.List.copyOf(ordersById.keySet())) cancelOrder(id);
      throw new IllegalStateException("Account risk limit triggered; new orders suspended");
    }
    return equity;
  }

  @jakarta.annotation.PreDestroy
  void closeLedger() {
    if (ledger != null) ledger.close();
  }

  private final ConcurrentMap<String, SimOrder> ordersById = new ConcurrentHashMap<>();
  private final ConcurrentMap<String, Position> positionsByTokenId = new ConcurrentHashMap<>();
  private final ConcurrentMap<String, TokenMeta> metaByTokenId = new ConcurrentHashMap<>();

  @PostConstruct
  void logSimConfig() {
    if (!enabled()) {
      log.info("paper-exchange simulator disabled");
      return;
    }
    if (hft.mode() != HftProperties.TradingMode.PAPER)
      throw new IllegalStateException("Simulator requires PAPER mode");
    ledger =
        new com.polybot.hft.risk.AccountLedger(
            java.nio.file.Path.of(statePath),
            objectMapper,
            initialCash,
            new com.polybot.hft.risk.AccountLedger.Limits(
                maxOrder, maxTokenExposure, maxGrossExposure, dailyLoss, drawdown),
            clock);
    // Recover outstanding paper orders from their durable reservations. No fill is invented during
    // downtime.
    for (var e : ledger.snapshot().orders().entrySet()) {
      var o = e.getValue();
      ordersById.put(
          e.getKey(),
          new SimOrder(
              e.getKey(),
              o.token(),
              o.buy() ? OrderSide.BUY : OrderSide.SELL,
              o.price(),
              o.original(),
              clock.instant(),
              o.status(),
              o.filled(),
              o.remaining()));
    }
    ledger
        .snapshot()
        .holdings()
        .forEach((token, h) -> positionsByTokenId.put(token, new Position(h.shares(), h.basis())));
    var recoveredTokens = new java.util.HashSet<>(ledger.snapshot().holdings().keySet());
    ledger.snapshot().orders().values().forEach(o -> recoveredTokens.add(o.token()));
    if (!recoveredTokens.isEmpty())
      marketWs.subscribeAssets(java.util.List.copyOf(recoveredTokens));
    log.info(
        "paper-exchange simulator enabled (fillsEnabled={}, fillPollMillis={}, makerP0={},"
            + " makerMultPerTick={}, makerPMax={}, makerFillFrac={})",
        sim.fillsEnabled(),
        sim.fillPollMillis(),
        sim.makerFillProbabilityPerPoll(),
        sim.makerFillProbabilityMultiplierPerTick(),
        sim.makerFillProbabilityMaxPerPoll(),
        sim.makerFillFractionOfRemaining());
  }

  public boolean enabled() {
    return Boolean.TRUE.equals(sim.enabled());
  }

  public synchronized OrderSubmissionResult placeLimitOrder(LimitOrderRequest request) {
    Objects.requireNonNull(request, "request");
    if (!enabled() || recoveryBlocked) throw new IllegalStateException("Paper account unavailable");
    if (hft.risk().killSwitch()) throw new IllegalStateException("Kill switch active");
    equity();
    var constraints = marketPolicy.resolve(request.tokenId());
    constraints.validate(request, clock);
    TopOfBook book =
        marketWs
            .getTopOfBook(request.tokenId())
            .orElseThrow(() -> new IllegalStateException("No live book"));
    if (book.updatedAt() == null
        || java.time.Duration.between(book.updatedAt(), clock.instant()).toMillis() > 2000)
      throw new IllegalStateException("Stale live book");
    if (request.side() == OrderSide.BUY && request.price().compareTo(book.bestAsk()) >= 0)
      throw new IllegalArgumentException("Post-only order would cross");
    if (request.side() == OrderSide.SELL && request.price().compareTo(book.bestBid()) <= 0)
      throw new IllegalArgumentException("Post-only order would cross");
    marketWs.subscribeAssets(List.of(request.tokenId()));
    String orderId =
        request.clientOrderId() == null ? "sim-" + UUID.randomUUID() : request.clientOrderId();
    SimOrder previous = ordersById.get(orderId);
    if (previous != null) {
      if (!previous.tokenId.equals(request.tokenId())
          || previous.side != request.side()
          || previous.requestedPrice.compareTo(request.price()) != 0
          || previous.requestedSize.compareTo(request.size()) != 0)
        throw new IllegalArgumentException("Idempotency key conflict");
      return new OrderSubmissionResult(
          hft.mode(),
          null,
          objectMapper.createObjectNode().put("orderID", orderId).put("status", previous.status));
    }
    BigDecimal size = request.size() == null ? BigDecimal.ZERO : request.size();
    BigDecimal matched = BigDecimal.ZERO;
    BigDecimal remaining = size.max(BigDecimal.ZERO);

    SimOrder order =
        new SimOrder(
            orderId,
            request.tokenId(),
            request.side(),
            request.price(),
            size,
            Instant.now(clock),
            "OPEN",
            matched,
            remaining);
    ledger.reserve(
        orderId, request.tokenId(), request.side() == OrderSide.BUY, request.price(), size);
    ordersById.put(orderId, order);
    publishOrderStatus(order, null);

    ObjectNode resp =
        objectMapper
            .createObjectNode()
            .put("mode", "SIM")
            .put("orderID", orderId)
            .put("orderId", orderId)
            .put("status", "OPEN");
    return new OrderSubmissionResult(hft.mode(), null, resp);
  }

  public OrderSubmissionResult placeMarketOrder(MarketOrderRequest request) {
    throw new UnsupportedOperationException(
        "Market/taker simulation is disabled until phase-2 depth and fee replay is validated");
  }

  public synchronized JsonNode cancelOrder(String orderId) {
    if (orderId == null || orderId.isBlank()) {
      return objectMapper.createObjectNode().put("canceled", false);
    }
    SimOrder order = ordersById.get(orderId);
    if (order == null) {
      return objectMapper
          .createObjectNode()
          .put("mode", "SIM")
          .put("canceled", false)
          .put("orderId", orderId);
    }
    synchronized (order) {
      if (isTerminal(order.status)) {
        return objectMapper
            .createObjectNode()
            .put("mode", "SIM")
            .put("canceled", false)
            .put("orderId", orderId)
            .put("status", order.status);
      }
      ledger.cancel(orderId);
      order.status = "CANCELED";
    }
    publishOrderStatus(order, null);
    return objectMapper
        .createObjectNode()
        .put("mode", "SIM")
        .put("canceled", true)
        .put("orderId", orderId)
        .put("status", "CANCELED");
  }

  public synchronized JsonNode getOrders(Map<String, String> query) {
    ArrayNode rows = objectMapper.createArrayNode();
    for (SimOrder order : ordersById.values()) {
      if (isTerminal(order.status)) continue;
      String token = query.get("asset_id");
      if (token != null && !token.equals(order.tokenId)) continue;
      rows.add(
          objectMapper
              .createObjectNode()
              .put("id", order.orderId)
              .put("asset_id", order.tokenId)
              .put("status", order.status)
              .put("price", order.requestedPrice.toPlainString())
              .put("original_size", order.requestedSize.toPlainString())
              .put("size_matched", order.matchedSize.toPlainString()));
    }
    return objectMapper.createObjectNode().set("data", rows);
  }

  public JsonNode getOrder(String orderId) {
    if (orderId == null || orderId.isBlank()) {
      return objectMapper.createObjectNode().put("error", "orderId blank");
    }
    SimOrder order = ordersById.get(orderId);
    if (order == null) {
      return objectMapper
          .createObjectNode()
          .put("mode", "SIM")
          .put("orderId", orderId)
          .put("status", "UNKNOWN");
    }
    synchronized (order) {
      return objectMapper
          .createObjectNode()
          .put("mode", "SIM")
          .put("orderId", order.orderId)
          .put("tokenId", order.tokenId)
          .put("side", order.side == null ? null : order.side.name())
          .put("status", order.status)
          .put("matched_size", order.matchedSize == null ? 0.0 : order.matchedSize.doubleValue())
          .put(
              "remaining_size",
              order.remainingSize == null ? 0.0 : order.remainingSize.doubleValue())
          .put(
              "requestedPrice",
              order.requestedPrice == null ? null : order.requestedPrice.doubleValue())
          .put(
              "requestedSize",
              order.requestedSize == null ? null : order.requestedSize.doubleValue());
    }
  }

  public PolymarketPosition[] getPositions(int limit, int offset) {
    if (limit <= 0) {
      limit = 200;
    }
    if (offset < 0) {
      offset = 0;
    }

    List<Map.Entry<String, Position>> snapshot = new ArrayList<>(positionsByTokenId.entrySet());
    snapshot.sort(Comparator.comparing(Map.Entry::getKey));

    int from = Math.min(offset, snapshot.size());
    int to = Math.min(snapshot.size(), from + limit);
    List<PolymarketPosition> out = new ArrayList<>();
    for (int i = from; i < to; i++) {
      Map.Entry<String, Position> e = snapshot.get(i);
      if (e == null) {
        continue;
      }
      String tokenId = e.getKey();
      Position p = e.getValue();
      if (tokenId == null || p == null) {
        continue;
      }
      BigDecimal shares = p.shares();
      if (shares == null || shares.compareTo(BigDecimal.ZERO) == 0) {
        continue;
      }
      TokenMeta meta = resolveTokenMeta(tokenId).orElse(null);
      out.add(
          new PolymarketPosition(
              sim.proxyAddress(),
              tokenId,
              meta == null ? null : meta.conditionId(),
              shares,
              p.avgPrice(),
              p.costUsd(),
              null,
              null,
              null,
              meta == null ? null : bestEffortCurPrice(tokenId),
              false,
              null,
              meta == null ? null : meta.title(),
              meta == null ? null : meta.marketSlug(),
              meta == null ? null : meta.outcome(),
              meta == null ? null : meta.outcomeIndex(),
              null,
              null,
              null));
    }
    return out.toArray(PolymarketPosition[]::new);
  }

  @Scheduled(initialDelay = 5000, fixedDelay = 2000)
  void monitorAccount() {
    if (!enabled() || ledger == null) return;
    try {
      equity();
    } catch (RuntimeException e) {
      for (String id : java.util.List.copyOf(ordersById.keySet())) cancelOrder(id);
      log.warn("Paper account suspended: {}", e.getMessage());
    }
  }

  @Scheduled(initialDelayString = "5000", fixedDelayString = "${executor.sim.fill-poll-millis:250}")
  void simulateFills() {
    if (!enabled()) {
      return;
    }
    if (!Boolean.TRUE.equals(sim.fillsEnabled())) {
      return;
    }

    for (SimOrder order : ordersById.values()) {
      if (order == null) {
        continue;
      }
      simulateOne(order);
    }
  }

  private void simulateOne(SimOrder order) {
    if (order == null) {
      return;
    }
    if (order.side != OrderSide.BUY) {
      return;
    }

    TopOfBook tob = marketWs.getTopOfBook(order.tokenId).orElse(null);
    if (tob == null || tob.bestBid() == null || tob.bestAsk() == null || tob.updatedAt() == null) {
      return;
    }
    long ageMs = Math.max(0, Instant.now(clock).toEpochMilli() - tob.updatedAt().toEpochMilli());
    if (ageMs > 2_000) {
      return;
    }

    BigDecimal bestBid = tob.bestBid();
    BigDecimal bestAsk = tob.bestAsk();
    BigDecimal price = order.requestedPrice;
    if (price == null) {
      return;
    }

    // Crossed book -> fill immediately at best ask (taker-like).
    if (bestAsk.compareTo(price) <= 0) {
      fill(order, order.remainingSize, bestAsk, "TAKER");
      return;
    }

    // Maker-like fill heuristic: if we're at/above the best bid, we sometimes get hit.
    if (bestBid.compareTo(price) > 0) {
      return;
    }

    double p = sim.makerFillProbabilityPerPoll();
    if (p <= 0) {
      return;
    }

    // Queue/priority proxy: if we improve above the best bid, fill odds increase.
    int ticksAboveBestBid = 0;
    try {
      BigDecimal tickSize = BigDecimal.valueOf(0.01);
      BigDecimal diff = price.subtract(bestBid);
      if (diff.compareTo(BigDecimal.ZERO) > 0 && tickSize.compareTo(BigDecimal.ZERO) > 0) {
        ticksAboveBestBid = diff.divide(tickSize, 0, RoundingMode.DOWN).intValue();
      }
    } catch (Exception ignored) {
    }

    double mult = sim.makerFillProbabilityMultiplierPerTick();
    if (ticksAboveBestBid > 0 && mult > 0 && mult != 1.0) {
      p = p * Math.pow(mult, ticksAboveBestBid);
    }
    double maxP = sim.makerFillProbabilityMaxPerPoll();
    if (maxP > 0) {
      p = Math.min(p, maxP);
    }
    if (p <= 0) {
      return;
    }
    if (ThreadLocalRandom.current().nextDouble() > p) {
      return;
    }
    BigDecimal remaining;
    synchronized (order) {
      remaining = order.remainingSize;
      if (remaining == null
          || remaining.compareTo(BigDecimal.ZERO) <= 0
          || isTerminal(order.status)) {
        return;
      }
    }
    BigDecimal fill =
        remaining
            .multiply(BigDecimal.valueOf(sim.makerFillFractionOfRemaining()))
            .setScale(2, RoundingMode.DOWN);
    if (fill.compareTo(BigDecimal.valueOf(0.01)) < 0) {
      fill = remaining.min(BigDecimal.valueOf(0.01));
    }
    fill(order, fill, price, "MAKER");
  }

  private synchronized void fill(
      SimOrder order, BigDecimal fillSize, BigDecimal fillPrice, String kind) {
    if (order == null || fillSize == null || fillPrice == null) {
      return;
    }
    if (fillSize.compareTo(BigDecimal.ZERO) <= 0) {
      return;
    }

    BigDecimal applied;
    String nextStatus;
    BigDecimal matched;
    BigDecimal remaining;
    synchronized (order) {
      if (isTerminal(order.status)) {
        return;
      }
      remaining = order.remainingSize == null ? BigDecimal.ZERO : order.remainingSize;
      if (remaining.compareTo(BigDecimal.ZERO) <= 0) {
        return;
      }
      applied = fillSize.min(remaining).setScale(2, RoundingMode.DOWN);
      if (applied.compareTo(BigDecimal.valueOf(0.01)) < 0) {
        return;
      }
      matched = (order.matchedSize == null ? BigDecimal.ZERO : order.matchedSize).add(applied);
      remaining = remaining.subtract(applied);
      if (remaining.compareTo(BigDecimal.ZERO) < 0) {
        remaining = BigDecimal.ZERO;
      }
      ledger.fill(
          order.orderId + ":" + matched.toPlainString(),
          order.orderId,
          applied,
          fillPrice,
          BigDecimal.ZERO);
      order.matchedSize = matched;
      order.remainingSize = remaining;
      nextStatus = remaining.compareTo(BigDecimal.ZERO) == 0 ? "FILLED" : "PARTIALLY_FILLED";
      order.status = nextStatus;
    }

    // Update positions
    positionsByTokenId.compute(
        order.tokenId,
        (k, prev) -> {
          Position cur = prev == null ? new Position(BigDecimal.ZERO, BigDecimal.ZERO) : prev;
          BigDecimal shares = cur.shares.add(applied);
          BigDecimal cost = cur.costUsd.add(fillPrice.multiply(applied));
          return new Position(shares, cost);
        });

    publishOrderStatus(order, null);
    publishUserTrade(order, applied, fillPrice, kind);
  }

  private void publishUserTrade(
      SimOrder order, BigDecimal fillSize, BigDecimal fillPrice, String kind) {
    if (!events.isEnabled()) {
      return;
    }
    if (order == null || fillSize == null || fillPrice == null) {
      return;
    }
    TokenMeta meta = resolveTokenMeta(order.tokenId).orElse(null);
    long tsSeconds = Instant.now(clock).getEpochSecond();

    ObjectNode trade = objectMapper.createObjectNode();
    if (meta != null) {
      trade.put("slug", meta.marketSlug);
      trade.put("title", meta.title);
      trade.put("conditionId", meta.conditionId);
      trade.put("outcome", meta.outcome);
      trade.put("outcomeIndex", meta.outcomeIndex);
    }
    trade.put("asset", order.tokenId);
    trade.put("side", order.side == null ? "BUY" : order.side.name());
    trade.put("price", fillPrice.doubleValue());
    trade.put("size", fillSize.doubleValue());
    trade.put("timestamp", tsSeconds);
    trade.put("transactionHash", "");
    trade.put("simKind", kind == null ? "" : kind);

    Map<String, Object> data =
        Map.of(
            "username", sim.username(),
            "proxyAddress", sim.proxyAddress(),
            "trade", trade);
    String key = "simtrade:" + order.orderId + ":" + UUID.randomUUID();
    events.publish(Instant.ofEpochSecond(tsSeconds), USER_TRADE_EVENT_TYPE, key, data);
  }

  private Optional<TokenMeta> resolveTokenMeta(String tokenId) {
    if (tokenId == null || tokenId.isBlank()) {
      return Optional.empty();
    }
    TokenMeta cached = metaByTokenId.get(tokenId);
    if (cached != null) {
      return Optional.of(cached);
    }
    try {
      // NOTE: CLOB /markets does not reliably support token filters; use Gamma API.
      JsonNode arr =
          gammaClient.markets(Map.of("clob_token_ids", tokenId.trim(), "limit", "1"), Map.of());
      if (arr == null || !arr.isArray() || arr.isEmpty()) {
        return Optional.empty();
      }
      JsonNode m = arr.get(0);
      if (m == null || m.isNull()) {
        return Optional.empty();
      }
      String marketSlug = textOrNull(m.get("slug"));
      String title = textOrNull(m.get("question"));
      String conditionId = textOrNull(m.get("conditionId"));
      if (title == null) {
        title = marketSlug;
      }

      // Gamma encodes arrays as JSON strings (e.g. outcomes='["Up","Down"]').
      String outcome = "";
      int outcomeIndex = -1;
      String clobTokenIdsRaw = textOrNull(m.get("clobTokenIds"));
      String outcomesRaw = textOrNull(m.get("outcomes"));
      if (clobTokenIdsRaw != null && outcomesRaw != null) {
        try {
          JsonNode tokenIds = objectMapper.readTree(clobTokenIdsRaw);
          JsonNode outcomes = objectMapper.readTree(outcomesRaw);
          if (tokenIds != null && tokenIds.isArray() && outcomes != null && outcomes.isArray()) {
            for (int i = 0; i < tokenIds.size(); i++) {
              JsonNode tid = tokenIds.get(i);
              if (tid == null || tid.isNull()) {
                continue;
              }
              if (tokenId.trim().equals(tid.asText("").trim())) {
                outcomeIndex = i;
                JsonNode oc = i < outcomes.size() ? outcomes.get(i) : null;
                outcome = oc == null || oc.isNull() ? "" : oc.asText("");
                break;
              }
            }
          }
        } catch (Exception ignored) {
        }
      }

      TokenMeta meta =
          new TokenMeta(
              marketSlug == null ? "" : marketSlug,
              title == null ? "" : title,
              conditionId == null ? "" : conditionId,
              outcome,
              outcomeIndex);
      metaByTokenId.put(tokenId, meta);
      return Optional.of(meta);
    } catch (Exception e) {
      log.debug("sim token meta lookup failed tokenId={} error={}", suffix(tokenId), e.toString());
      return Optional.empty();
    }
  }

  private void publishOrderStatus(SimOrder order, String error) {
    if (!events.isEnabled()) {
      return;
    }
    if (order == null) {
      return;
    }
    String status;
    BigDecimal matched;
    BigDecimal remaining;
    synchronized (order) {
      status = order.status;
      matched = order.matchedSize == null ? BigDecimal.ZERO : order.matchedSize;
      remaining = order.remainingSize == null ? BigDecimal.ZERO : order.remainingSize;

      boolean changed =
          !Objects.equals(normalize(status), normalize(order.lastPublishedStatus))
              || !decimalEq(matched, order.lastPublishedMatched)
              || !decimalEq(remaining, order.lastPublishedRemaining)
              || error != null;
      if (!changed) {
        return;
      }
      order.lastPublishedStatus = status;
      order.lastPublishedMatched = matched;
      order.lastPublishedRemaining = remaining;
    }

    String orderJson;
    try {
      orderJson = objectMapper.writeValueAsString(getOrder(order.orderId));
    } catch (Exception ignored) {
      orderJson = null;
    }

    events.publish(
        clock.instant(),
        HftEventTypes.EXECUTOR_ORDER_STATUS,
        order.orderId,
        new ExecutorOrderStatusEvent(
            order.orderId,
            order.tokenId,
            order.side,
            order.requestedPrice,
            order.requestedSize,
            status,
            matched,
            remaining,
            orderJson,
            error));
  }

  private static boolean isTerminal(String status) {
    if (status == null) {
      return false;
    }
    String s = status.trim().toUpperCase(Locale.ROOT);
    return s.contains("FILLED")
        || s.contains("CANCELED")
        || s.contains("CANCELLED")
        || s.contains("EXPIRED")
        || s.contains("REJECTED")
        || s.contains("FAILED")
        || s.contains("DONE")
        || s.contains("CLOSED");
  }

  private static boolean decimalEq(BigDecimal a, BigDecimal b) {
    if (a == null && b == null) {
      return true;
    }
    if (a == null || b == null) {
      return false;
    }
    return a.compareTo(b) == 0;
  }

  private static String normalize(String s) {
    return s == null ? null : s.trim().toUpperCase(Locale.ROOT);
  }

  private static String textOrNull(JsonNode node) {
    if (node == null || node.isNull()) {
      return null;
    }
    String s = node.asText(null);
    return s == null || s.isBlank() ? null : s.trim();
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

  private BigDecimal bestEffortCurPrice(String tokenId) {
    try {
      TopOfBook tob = marketWs.getTopOfBook(tokenId).orElse(null);
      if (tob == null) {
        return null;
      }
      BigDecimal bid = tob.bestBid();
      BigDecimal ask = tob.bestAsk();
      if (bid == null || ask == null) {
        return null;
      }
      return bid.add(ask).divide(BigDecimal.valueOf(2), 6, RoundingMode.HALF_UP);
    } catch (Exception ignored) {
      return null;
    }
  }

  private record Position(BigDecimal shares, BigDecimal costUsd) {
    private BigDecimal avgPrice() {
      if (shares == null || shares.compareTo(BigDecimal.ZERO) == 0) {
        return null;
      }
      if (costUsd == null) {
        return null;
      }
      return costUsd.divide(shares, 6, RoundingMode.HALF_UP);
    }
  }

  private record TokenMeta(
      String marketSlug, String title, String conditionId, String outcome, int outcomeIndex) {}

  private static final class SimOrder {
    private final String orderId;
    private final String tokenId;
    private final OrderSide side;
    private final BigDecimal requestedPrice;
    private final BigDecimal requestedSize;
    private final Instant createdAt;

    private String status;
    private BigDecimal matchedSize;
    private BigDecimal remainingSize;

    private String lastPublishedStatus;
    private BigDecimal lastPublishedMatched;
    private BigDecimal lastPublishedRemaining;

    private SimOrder(
        String orderId,
        String tokenId,
        OrderSide side,
        BigDecimal requestedPrice,
        BigDecimal requestedSize,
        Instant createdAt,
        String status,
        BigDecimal matchedSize,
        BigDecimal remainingSize) {
      this.orderId = orderId;
      this.tokenId = tokenId;
      this.side = side;
      this.requestedPrice = requestedPrice;
      this.requestedSize = requestedSize;
      this.createdAt = createdAt;
      this.status = status;
      this.matchedSize = matchedSize;
      this.remainingSize = remainingSize;
    }
  }
}
