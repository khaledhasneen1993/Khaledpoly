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

  private final @NonNull com.polybot.hft.paper.PaperJournal journal;

  @org.springframework.beans.factory.annotation.Value("${paper.matching.activation-ms:250}")
  private long activationMillis;

  @org.springframework.beans.factory.annotation.Value("${paper.matching.cancel-ms:250}")
  private long cancelMillis;

  @org.springframework.beans.factory.annotation.Value("${paper.matching.queue-multiplier:2}")
  private BigDecimal queueMultiplier;

  private com.polybot.hft.paper.PaperMatchingEngine matching;
  private final com.polybot.hft.paper.PaperMetrics metrics =
      new com.polybot.hft.paper.PaperMetrics();

  public synchronized Map<String, Object> paperMetrics() {
    if (!enabled() || ledger == null || matching == null)
      throw new IllegalStateException("Paper account unavailable");
    var result = new java.util.LinkedHashMap<String, Object>(metrics.snapshot(clock.millis()));
    BigDecimal total = BigDecimal.ZERO, paired = BigDecimal.ZERO, residual = BigDecimal.ZERO;
    for (var pair : pairs.values()) {
      BigDecimal up = BigDecimal.ZERO, down = BigDecimal.ZERO;
      for (var o : ledger.snapshot().orders().values())
        if (o.buy()) {
          if (o.token().equals(pair.up())) up = up.add(o.filled());
          if (o.token().equals(pair.down())) down = down.add(o.filled());
        }
      total = total.add(up).add(down);
      paired = paired.add(up.min(down).multiply(BigDecimal.valueOf(2)));
      if (!clock.instant().isBefore(pair.end())) {
        var holdings = ledger.snapshot().holdings();
        BigDecimal uq =
            holdings
                .getOrDefault(
                    pair.up(),
                    new com.polybot.hft.risk.AccountLedger.Holding(
                        BigDecimal.ZERO, BigDecimal.ZERO))
                .shares();
        BigDecimal dq =
            holdings
                .getOrDefault(
                    pair.down(),
                    new com.polybot.hft.risk.AccountLedger.Holding(
                        BigDecimal.ZERO, BigDecimal.ZERO))
                .shares();
        residual = residual.add(uq.subtract(dq).abs());
      }
    }
    result.put(
        "quantityPairCompletion",
        total.signum() == 0 ? null : paired.divide(total, 8, RoundingMode.DOWN));
    result.put("residualExpiryWorstCaseNotional", residual);
    result.put("dataGaps", matching.gaps());
    result.put("duplicatePrintsSuppressed", matching.duplicates());
    result.put("availableCash", ledger.availableCash());
    result.put("netRealizedPnl", ledger.snapshot().realized());
    result.put("feesAndSettlementCosts", ledger.snapshot().fees());
    result.put("halted", ledger.snapshot().halted() || recoveryBlocked);
    return result;
  }

  private com.polybot.hft.risk.AccountLedger ledger;
  private volatile boolean recoveryBlocked;

  private record PairMarket(
      String condition, String up, String down, Instant end, Instant unhedgedAt) {}

  private final Map<String, PairMarket> pairs = new java.util.TreeMap<>();
  private com.polybot.hft.state.AtomicJsonState pairFile;

  @org.springframework.beans.factory.annotation.Value("${paper.settlement.merge-cost:0.01}")
  private BigDecimal mergeCost;

  @org.springframework.beans.factory.annotation.Value("${paper.portfolio.gross-budget:100}")
  private BigDecimal portfolioBudget;

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
    journal.record("ACCOUNT_MARK", null, marks);
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
    if (pairFile != null) pairFile.close();
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
    if (mergeCost.signum() < 0 || portfolioBudget.signum() <= 0)
      throw new IllegalArgumentException("Invalid paper cost/budget");
    ledger =
        new com.polybot.hft.risk.AccountLedger(
            java.nio.file.Path.of(statePath),
            objectMapper,
            initialCash,
            new com.polybot.hft.risk.AccountLedger.Limits(
                maxOrder, maxTokenExposure, maxGrossExposure, dailyLoss, drawdown),
            clock);
    pairFile =
        new com.polybot.hft.state.AtomicJsonState(
            java.nio.file.Path.of(statePath + ".pairs"), objectMapper);
    var savedPairs = pairFile.load();
    if (savedPairs != null)
      savedPairs
          .fields()
          .forEachRemaining(
              e ->
                  pairs.put(e.getKey(), objectMapper.convertValue(e.getValue(), PairMarket.class)));
    matching =
        new com.polybot.hft.paper.PaperMatchingEngine(
            activationMillis, cancelMillis, 2000, queueMultiplier);
    journal.record(
        "MATCHING_CONFIG",
        null,
        Map.of(
            "activationMs",
            activationMillis,
            "cancelMs",
            cancelMillis,
            "queueMultiplier",
            queueMultiplier,
            "maxBookAgeMs",
            2000,
            "fillsEnabled",
            sim.fillsEnabled(),
            "account",
            ledger.snapshot(),
            "pairs",
            pairs,
            "mergeCost",
            mergeCost,
            "portfolioBudget",
            portfolioBudget,
            "limits",
            new com.polybot.hft.risk.AccountLedger.Limits(
                maxOrder, maxTokenExposure, maxGrossExposure, dailyLoss, drawdown)));
    // Recover outstanding paper orders from their durable reservations. No fill is invented during
    // downtime.
    for (var e : ledger.snapshot().orders().entrySet()) {
      var o = e.getValue();
      // Queue priority cannot be reconstructed across downtime. Cancel; never reset it to zero.
      if (o.remaining().signum() > 0) {
        ledger.cancel(e.getKey());
        o = ledger.snapshot().orders().get(e.getKey());
      }
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
    marketWs.onTape(this::onMarketTape);
    log.info(
        "Paper matching model conservative-l2-v1 (fillsEnabled={}; activation={}ms; cancel={}ms;"
            + " queue={})",
        sim.fillsEnabled(),
        activationMillis,
        cancelMillis,
        queueMultiplier);
  }

  public boolean enabled() {
    return Boolean.TRUE.equals(sim.enabled());
  }

  public synchronized OrderSubmissionResult placeLimitOrder(LimitOrderRequest request) {
    Objects.requireNonNull(request, "request");
    if (!enabled() || recoveryBlocked) throw new IllegalStateException("Paper account unavailable");
    if (hft.risk().killSwitch()) throw new IllegalStateException("Kill switch active");
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
    equity();
    validateMaker(request);
    marketWs.subscribeAssets(List.of(request.tokenId()));
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
    if (!ledger.snapshot().orders().containsKey(orderId))
      ledger.reserve(
          orderId, request.tokenId(), request.side() == OrderSide.BUY, request.price(), size);
    ordersById.put(orderId, order);
    matchingInput(
        "ORDER",
        objectMapper.valueToTree(
            Map.of(
                "id",
                orderId,
                "token",
                request.tokenId(),
                "side",
                request.side().name(),
                "price",
                request.price().toPlainString(),
                "size",
                size.toPlainString())));
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

  public com.polybot.hft.polymarket.model.MarketConstraints marketConstraints(String token) {
    return marketPolicy.resolve(token);
  }

  private void validateMaker(LimitOrderRequest request) {
    var constraints = marketPolicy.resolve(request.tokenId());
    constraints.validate(request, clock);
    journal.record(
        "MARKET_CONSTRAINTS", null, Map.of("token", request.tokenId(), "constraints", constraints));
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
  }

  public synchronized Object placePair(com.polybot.hft.polymarket.api.PaperPairRequest pair) {
    var up = Objects.requireNonNull(pair.up());
    var down = Objects.requireNonNull(pair.down());
    if (!enabled() || recoveryBlocked || hft.risk().killSwitch())
      throw new IllegalStateException("Paper account unavailable");
    if (ordersById.containsKey(up.clientOrderId())
        || ordersById.containsKey(down.clientOrderId())) {
      if (!ordersById.containsKey(up.clientOrderId())
          || !ordersById.containsKey(down.clientOrderId()))
        throw new IllegalStateException("Incomplete pair recovery required");
      return List.of(placeLimitOrder(up), placeLimitOrder(down));
    }
    var holdings = ledger.snapshot().holdings();
    BigDecimal heldUp =
        holdings
            .getOrDefault(
                up.tokenId(),
                new com.polybot.hft.risk.AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
            .shares();
    BigDecimal heldDown =
        holdings
            .getOrDefault(
                down.tokenId(),
                new com.polybot.hft.risk.AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
            .shares();
    if (heldUp.compareTo(heldDown) != 0)
      throw new IllegalStateException("Existing unhedged inventory blocks new pairs");
    equity();
    validateMaker(up);
    validateMaker(down);
    var uc = marketPolicy.resolve(up.tokenId());
    var dc = marketPolicy.resolve(down.tokenId());
    if (!uc.condition().equals(dc.condition())
        || uc.negativeRisk()
        || dc.negativeRisk()
        || up.tokenId().equals(down.tokenId())
        || up.side() != OrderSide.BUY
        || down.side() != OrderSide.BUY
        || up.size().compareTo(down.size()) != 0
        || up.clientOrderId() == null
        || down.clientOrderId() == null
        || up.price().add(down.price()).compareTo(BigDecimal.ONE) >= 0)
      throw new IllegalArgumentException("Invalid binary complete set");
    // MarketPolicy verifies membership; reject markets with more than two outcomes before
    // merge/pairing.
    if (!marketPolicy.binaryPair(up.tokenId(), down.tokenId()))
      throw new IllegalArgumentException("Not a verified binary pair");
    BigDecimal gross =
        ledger.snapshot().holdings().values().stream()
            .map(com.polybot.hft.risk.AccountLedger.Holding::basis)
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    for (var order : ledger.snapshot().orders().values())
      if (order.buy()) gross = gross.add(order.price().multiply(order.remaining()));
    if (gross.add(up.price().add(down.price()).multiply(up.size())).compareTo(portfolioBudget) > 0)
      throw new IllegalStateException("Correlated portfolio budget exceeded");
    PairMarket registration =
        new PairMarket(uc.condition(), up.tokenId(), down.tokenId(), uc.endTime(), null);
    pairs.put(uc.condition(), registration);
    pairFile.save(pairs);
    journal.record("PAIR_MARKET", null, registration);
    journal.record("PAIR_RESERVATION", null, pair);
    ledger.reservePair(
        up.clientOrderId(),
        up.tokenId(),
        down.clientOrderId(),
        down.tokenId(),
        up.price(),
        down.price(),
        up.size());
    try {
      return List.of(placeLimitOrder(up), placeLimitOrder(down));
    } catch (RuntimeException e) {
      recoveryBlocked = true;
      ledger.halt();
      matchingInput("GAP", objectMapper.valueToTree(Map.of("reason", "pair_submission_failed")));
      ledger.cancel(up.clientOrderId());
      ledger.cancel(down.clientOrderId());
      throw e;
    }
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
      matchingInput("CANCEL", objectMapper.valueToTree(Map.of("id", orderId)));
    }
    publishOrderStatus(order, null);
    return objectMapper
        .createObjectNode()
        .put("mode", "SIM")
        .put("canceled", isTerminal(order.status))
        .put("pending", !isTerminal(order.status))
        .put("orderId", orderId)
        .put("status", order.status);
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

  @Scheduled(initialDelay = 100, fixedDelay = 50)
  synchronized void simulateFills() {
    if (enabled() && matching != null) {
      matchingInput("TICK", objectMapper.createObjectNode());
      checkPairRisk();
    }
  }

  private synchronized void onMarketTape(String kind, JsonNode data) {
    if (!enabled() || matching == null) return;
    if (kind.equals("TRADE") && !sim.fillsEnabled()) return;
    try {
      matchingInput(kind, data);
    } catch (RuntimeException e) {
      recoveryBlocked = true;
      ledger.halt();
      for (var order : ordersById.values())
        if (!isTerminal(order.status)) {
          ledger.cancel(order.orderId);
          order.status = "CANCELED";
          publishOrderStatus(order, e.getMessage());
        }
      throw e;
    }
  }

  private void matchingInput(String kind, JsonNode data) {
    long at =
        journal.record(
            "MATCH_" + kind, data.has("sourceMs") ? data.path("sourceMs").asLong() : null, data);
    var update = matching.accept(kind, at, data);
    if (kind.equals("BOOK")) metrics.book(data, at);
    for (var f : update.fills()) {
      fill(ordersById.get(f.id()), f.size(), f.price(), "MAKER");
      metrics.fill(f);
      journal.record("PAPER_FILL", null, f);
    }
    update
        .terminal()
        .forEach(
            (id, status) -> {
              SimOrder order = ordersById.get(id);
              if (order == null) return;
              if (!status.equals("FILLED")) ledger.cancel(id);
              order.status = status;
              publishOrderStatus(order, null);
            });
    if (!update.fills().isEmpty()) {
      mergeCompleteSets();
      updatePairRiskTimes();
    }
  }

  private void updatePairRiskTimes() {
    boolean changed = false;
    for (var pair : List.copyOf(pairs.values())) {
      var h = ledger.snapshot().holdings();
      BigDecimal up =
          h.getOrDefault(
                  pair.up(),
                  new com.polybot.hft.risk.AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .shares();
      BigDecimal down =
          h.getOrDefault(
                  pair.down(),
                  new com.polybot.hft.risk.AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .shares();
      Instant since =
          up.compareTo(down) == 0
              ? null
              : pair.unhedgedAt() == null ? clock.instant() : pair.unhedgedAt();
      if (!Objects.equals(since, pair.unhedgedAt())) {
        var next = new PairMarket(pair.condition(), pair.up(), pair.down(), pair.end(), since);
        pairs.put(pair.condition(), next);
        journal.record("PAIR_RISK_CLOCK", null, next);
        changed = true;
      }
    }
    if (changed) pairFile.save(pairs);
  }

  private void checkPairRisk() {
    if (recoveryBlocked) return;
    for (var pair : pairs.values()) {
      var h = ledger.snapshot().holdings();
      BigDecimal up =
          h.getOrDefault(
                  pair.up(),
                  new com.polybot.hft.risk.AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .shares();
      BigDecimal down =
          h.getOrDefault(
                  pair.down(),
                  new com.polybot.hft.risk.AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .shares();
      BigDecimal imbalance = up.subtract(down).abs();
      if (imbalance.signum() > 0
          && (pair.unhedgedAt() == null
              || java.time.Duration.between(pair.unhedgedAt(), clock.instant()).toMillis() >= 30000
              || imbalance.compareTo(new BigDecimal("25")) >= 0)) {
        recoveryBlocked = true;
        ledger.halt();
        journal.record(
            "RISK_HALT",
            null,
            Map.of(
                "reason",
                "unhedged_age_or_size",
                "condition",
                pair.condition(),
                "shares",
                imbalance));
        matchingInput("GAP", objectMapper.valueToTree(Map.of("reason", "unhedged_risk")));
        return;
      }
    }
  }

  private void mergeCompleteSets() {
    for (var pair : pairs.values()) {
      var holdings = ledger.snapshot().holdings();
      BigDecimal up =
          holdings
              .getOrDefault(
                  pair.up(),
                  new com.polybot.hft.risk.AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .shares();
      BigDecimal down =
          holdings
              .getOrDefault(
                  pair.down(),
                  new com.polybot.hft.risk.AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .shares();
      BigDecimal quantity = up.min(down);
      if (quantity.compareTo(mergeCost) <= 0) continue;
      String operation = "paper-merge:" + UUID.randomUUID();
      journal.record(
          "MERGE",
          null,
          Map.of(
              "id",
              operation,
              "up",
              pair.up(),
              "down",
              pair.down(),
              "quantity",
              quantity,
              "cost",
              mergeCost));
      ledger.merge(operation, pair.up(), pair.down(), quantity, mergeCost);
      for (String token : List.of(pair.up(), pair.down())) {
        var h = ledger.snapshot().holdings().get(token);
        positionsByTokenId.put(token, new Position(h.shares(), h.basis()));
      }
    }
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
      applied = fillSize.min(remaining);
      if (applied.signum() <= 0) {
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

    var holding = ledger.snapshot().holdings().get(order.tokenId);
    positionsByTokenId.put(order.tokenId, new Position(holding.shares(), holding.basis()));

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
    return com.polybot.hft.polymarket.model.OrderStatus.terminal(status);
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
