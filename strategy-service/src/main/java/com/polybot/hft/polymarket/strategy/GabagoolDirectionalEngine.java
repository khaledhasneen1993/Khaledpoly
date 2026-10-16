package com.polybot.hft.polymarket.strategy;

import com.polybot.hft.config.HftProperties;
import com.polybot.hft.events.HftEventPublisher;
import com.polybot.hft.polymarket.strategy.config.GabagoolConfig;
import com.polybot.hft.polymarket.strategy.model.Direction;
import com.polybot.hft.polymarket.strategy.model.GabagoolMarket;
import com.polybot.hft.polymarket.strategy.model.MarketInventory;
import com.polybot.hft.polymarket.strategy.model.OrderState;
import com.polybot.hft.polymarket.strategy.service.BankrollService;
import com.polybot.hft.polymarket.strategy.service.OrderManager;
import com.polybot.hft.polymarket.strategy.service.OrderManager.CancelReason;
import com.polybot.hft.polymarket.strategy.service.PositionTracker;
import com.polybot.hft.polymarket.strategy.service.QuoteCalculator;
import com.polybot.hft.polymarket.ws.ClobMarketWebSocketClient;
import com.polybot.hft.polymarket.ws.TopOfBook;
import com.polybot.hft.strategy.executor.ExecutorApiClient;
import com.polybot.hft.strategy.metrics.StrategyMetricsService;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.Stream;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/** Gabagool22-style strategy for Up/Down binary markets (replica-oriented). */
@Component
@Slf4j
@RequiredArgsConstructor
public class GabagoolDirectionalEngine {

  private static final Duration TICK_SIZE_CACHE_TTL = Duration.ofSeconds(30);

  @org.springframework.beans.factory.annotation.Value("${paper.settlement.merge-cost:0.01}")
  private BigDecimal mergeCost;

  @org.springframework.beans.factory.annotation.Value("${paper.matching.activation-ms:250}")
  private long activationMs;

  private final @NonNull HftProperties properties;
  private final @NonNull ClobMarketWebSocketClient marketWs;
  private final @NonNull ExecutorApiClient executorApi;
  private final @NonNull HftEventPublisher events;
  private final @NonNull GabagoolMarketDiscovery marketDiscovery;
  private final @NonNull Clock clock;
  private final @NonNull StrategyMetricsService metricsService;

  private final ScheduledExecutorService executor =
      Executors.newSingleThreadScheduledExecutor(
          r -> {
            Thread t = new Thread(r, "gabagool-directional");
            t.setDaemon(true);
            return t;
          });

  private final String runId = UUID.randomUUID().toString();
  private final AtomicReference<List<GabagoolMarket>> activeMarkets =
      new AtomicReference<>(List.of());
  private final Map<String, BigDecimal> lastMid = new HashMap<>(),
      volatilityByMarket = new HashMap<>();
  private final Map<String, Instant> unhedgedSince = new HashMap<>();
  private final Map<String, TickSizeEntry> tickSizeCache = new ConcurrentHashMap<>();

  // Services (initialized in startIfEnabled)
  private BankrollService bankrollService;
  private PositionTracker positionTracker;
  private QuoteCalculator quoteCalculator;
  private OrderManager orderManager;

  @PostConstruct
  void startIfEnabled() {
    GabagoolConfig cfg = getConfig();
    logStartupConfig(cfg);
    events.publish("strategy.config", runId, cfg);

    if (!cfg.enabled()) {
      log.info("gabagool-directional strategy is disabled");
      return;
    }

    if (!properties.polymarket().marketWsEnabled()) {
      log.warn("gabagool-directional enabled, but market WS disabled");
      return;
    }

    // Initialize services
    bankrollService = new BankrollService(executorApi, metricsService, clock);
    positionTracker = new PositionTracker(executorApi, clock);
    quoteCalculator = new QuoteCalculator(bankrollService, properties, metricsService);
    orderManager = new OrderManager(executorApi, events, clock, runId);
    orderManager.setFillListener(this::handleFill);

    long periodMs = Math.max(100, cfg.refreshMillis());
    executor.scheduleAtFixedRate(() -> safeTick(cfg), 1000, periodMs, TimeUnit.MILLISECONDS);
    executor.scheduleAtFixedRate(this::discoverMarkets, 0, 30, TimeUnit.SECONDS);

    log.info("gabagool-directional started (refreshMillis={})", periodMs);
  }

  public int activeMarketCount() {
    return activeMarkets.get().size();
  }

  public boolean isRunning() {
    return !executor.isShutdown() && getConfig().enabled();
  }

  @PreDestroy
  void shutdown() {
    log.info("gabagool-directional shutting down");
    executor.shutdown();
    try {
      if (!executor.awaitTermination(10, TimeUnit.SECONDS)) executor.shutdownNow();
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      executor.shutdownNow();
    }
    if (orderManager != null) orderManager.cancelAll(CancelReason.SHUTDOWN);
    if (orderManager != null) orderManager.close();
  }

  private void safeTick(GabagoolConfig cfg) {
    try {
      tick(cfg);
    } catch (Exception e) {
      log.error("Strategy suspended: {}", e.toString());
      orderManager.cancelAll(CancelReason.BOOK_STALE);
    }
  }

  private void tick(GabagoolConfig cfg) {
    orderManager.reconcileOpenOrders();
    orderManager.checkPendingOrders(this::handleFill);
    positionTracker.refreshIfStale();
    bankrollService.refreshIfStale(cfg);
    positionTracker.syncInventory(activeMarkets.get());

    if (bankrollService.isBelowThreshold(cfg)) {
      log.warn(
          "CIRCUIT BREAKER: Effective bankroll below threshold ({}), skipping market evaluation",
          cfg.bankrollMinThreshold());
      orderManager.cancelAll(CancelReason.OUTSIDE_TIME_WINDOW);
      orderManager.checkPendingOrders(this::handleFill);
      return;
    }

    Instant now = clock.instant();
    for (GabagoolMarket market :
        activeMarkets.get().stream()
            .sorted(
                java.util.Comparator.comparing(this::visibleCost)
                    .thenComparing(GabagoolMarket::slug))
            .toList()) {
      try {
        evaluateMarket(market, cfg, now);
      } catch (Exception e) {
        log.error("Error evaluating market {}: {}", market.slug(), e.getMessage());
      }
    }

    orderManager.checkPendingOrders(this::handleFill);
  }

  private BigDecimal visibleCost(GabagoolMarket m) {
    var up = marketWs.getTopOfBook(m.upTokenId()).orElse(null);
    var down = marketWs.getTopOfBook(m.downTokenId()).orElse(null);
    return up == null || down == null || up.bestBid() == null || down.bestBid() == null
        ? BigDecimal.TEN
        : up.bestBid().add(down.bestBid());
  }

  private void handleFill(OrderState state, BigDecimal filledShares) {
    if (state.market() == null || state.direction() == null) return;
    positionTracker.recordFill(
        state.market().slug(), state.direction() == Direction.UP, filledShares, state.price());
    log.debug(
        "GABAGOOL: Updated inventory for {} after fill: {} +{} shares",
        state.market().slug(),
        state.direction(),
        filledShares);
  }

  private void evaluateMarket(GabagoolMarket market, GabagoolConfig cfg, Instant now) {
    long secondsToEnd = Duration.between(now, market.endTime()).getSeconds();
    long maxLifetimeSeconds =
        "updown-5m".equals(market.marketType())
            ? 300L
            : "updown-15m".equals(market.marketType()) ? 900L : 3600L;

    if (secondsToEnd < 0 || secondsToEnd > maxLifetimeSeconds) {
      orderManager.cancelMarketOrders(market, CancelReason.OUTSIDE_LIFETIME, secondsToEnd);
      return;
    }

    long minSecondsToEnd = Math.max(0L, cfg.minSecondsToEnd());
    long maxSecondsToEnd =
        Math.min(maxLifetimeSeconds, Math.max(minSecondsToEnd, cfg.maxSecondsToEnd()));
    if (secondsToEnd < minSecondsToEnd || secondsToEnd > maxSecondsToEnd) {
      orderManager.cancelMarketOrders(market, CancelReason.OUTSIDE_TIME_WINDOW, secondsToEnd);
      return;
    }

    TopOfBook upBook = marketWs.getTopOfBook(market.upTokenId()).orElse(null);
    TopOfBook downBook = marketWs.getTopOfBook(market.downTokenId()).orElse(null);

    if (upBook == null || downBook == null || isStale(upBook) || isStale(downBook)) {
      if (upBook == null || isStale(upBook)) {
        orderManager.cancelOrder(
            market.upTokenId(), CancelReason.BOOK_STALE, secondsToEnd, upBook, downBook);
      }
      if (downBook == null || isStale(downBook)) {
        orderManager.cancelOrder(
            market.downTokenId(), CancelReason.BOOK_STALE, secondsToEnd, downBook, upBook);
      }
      return;
    }

    MarketInventory inv = positionTracker.getInventory(market.slug());
    int[] skew = quoteCalculator.calculateSkewTicks(inv, cfg);
    int skewTicksUp = skew[0];
    int skewTicksDown = skew[1];

    // Phase 2: coordinated maker pairs. Legacy taker/top-up heuristics are never called.
    BigDecimal upTickSize = getTickSize(market.upTokenId()),
        downTickSize = getTickSize(market.downTokenId());
    if (upTickSize == null || downTickSize == null) return;
    BigDecimal up = quoteCalculator.calculateEntryPrice(upBook, upTickSize, cfg, skewTicksUp);
    BigDecimal down =
        quoteCalculator.calculateEntryPrice(downBook, downTickSize, cfg, skewTicksDown);
    if (up == null || down == null) return;
    BigDecimal depth =
        upBook.bestBidSize() == null || downBook.bestBidSize() == null
            ? BigDecimal.ZERO
            : upBook.bestBidSize().min(downBook.bestBidSize());
    if (depth.signum() <= 0) return;
    BigDecimal mid = upBook.bestBid().add(upBook.bestAsk()).divide(BigDecimal.valueOf(2));
    BigDecimal previous = lastMid.put(market.slug(), mid);
    BigDecimal movement = previous == null ? BigDecimal.ZERO : mid.subtract(previous).abs();
    BigDecimal volatility =
        volatilityByMarket.merge(
            market.slug(),
            movement,
            (a, b) -> a.multiply(new BigDecimal("0.9")).add(b.multiply(new BigDecimal("0.1"))));
    BigDecimal required =
        com.polybot.hft.paper.PairPolicy.requiredEdge(
            BigDecimal.valueOf(cfg.completeSetMinEdge()),
            volatility,
            secondsToEnd,
            depth,
            activationMs,
            inv.imbalance());
    BigDecimal edge =
        BigDecimal.ONE.subtract(up).subtract(down); // maker fees zero; no assumed incentives
    events.publish(
        "strategy.pair.decision",
        market.slug(),
        Map.of(
            "edge",
            edge,
            "requiredEdge",
            required,
            "imbalance",
            inv.imbalance(),
            "depth",
            depth,
            "secondsToEnd",
            secondsToEnd));
    if (inv.imbalance().signum() != 0) {
      Instant observed = unhedgedSince.computeIfAbsent(market.slug(), k -> now);
      // A restarted strategy cannot establish how old recovered unhedged inventory is.
      boolean unknownAge = inv.lastUpFillAt() == null && inv.lastDownFillAt() == null;
      boolean overdue =
          unknownAge
              || Duration.between(observed, now).getSeconds() >= 30
              || inv.imbalance().abs().compareTo(new BigDecimal("25")) >= 0;
      if (overdue) {
        orderManager.cancelMarketOrders(market, CancelReason.OUTSIDE_TIME_WINDOW, secondsToEnd);
        events.publish(
            "strategy.risk.unhedged",
            market.slug(),
            Map.of(
                "shares",
                inv.imbalance(),
                "unknownAge",
                unknownAge,
                "action",
                "SUSPEND_MARKET_REQUIRES_RECONCILIATION"));
      }
      return; // Existing second-leg reservation stays intact until fill, cancellation, or timeout.
    }
    unhedgedSince.remove(market.slug());
    if (edge.compareTo(required) < 0) {
      orderManager.cancelMarketOrders(market, CancelReason.INSUFFICIENT_EDGE, secondsToEnd);
      return;
    }
    // Avoid price churn: retain both resting orders until the configured minimum lifetime.
    var uo = orderManager.getOrder(market.upTokenId());
    var dO = orderManager.getOrder(market.downTokenId());
    if (uo != null || dO != null) {
      var oldest = uo != null ? uo : dO;
      if (Duration.between(oldest.placedAt(), now).toMillis()
          < Math.max(2000, cfg.minReplaceMillis())) return;
      if (uo != null
          && dO != null
          && uo.price().compareTo(up) == 0
          && dO.price().compareTo(down) == 0) return;
      orderManager.cancelMarketOrders(market, CancelReason.REPLACE_PRICE, secondsToEnd);
      return;
    }
    BigDecimal exposure =
        quoteCalculator.calculateExposure(
            orderManager.getOpenOrders(), positionTracker.getAllInventories());
    BigDecimal us = quoteCalculator.calculateShares(market, up, cfg, secondsToEnd, exposure);
    BigDecimal ds = quoteCalculator.calculateShares(market, down, cfg, secondsToEnd, exposure);
    if (us == null || ds == null) return;
    BigDecimal quantity =
        us.min(ds).min(depth.multiply(new BigDecimal("0.1"))).setScale(2, RoundingMode.DOWN);
    // BTC and ETH share one conservative crypto risk budget; no diversification credit.
    BigDecimal correlated = positionTracker.grossBasis();
    for (var order : orderManager.getOpenOrders().values())
      correlated =
          correlated.add(
              order
                  .price()
                  .multiply(
                      order
                          .size()
                          .subtract(
                              order.matchedSize() == null ? BigDecimal.ZERO : order.matchedSize())
                          .max(BigDecimal.ZERO)));
    BigDecimal budget = new BigDecimal("100").subtract(correlated);
    if (budget.signum() <= 0) return;
    quantity = quantity.min(budget.divide(up.add(down), 2, RoundingMode.DOWN));
    var uc = executorApi.getMarketConstraints(market.upTokenId());
    var dc = executorApi.getMarketConstraints(market.downTokenId());
    if (quantity.compareTo(uc.minSize().max(dc.minSize())) < 0
        || !uc.condition().equals(dc.condition())) return;
    if (edge.multiply(quantity).subtract(mergeCost).compareTo(required.multiply(quantity)) < 0)
      return;
    if (quantity.signum() > 0) orderManager.placePair(market, up, down, quantity, secondsToEnd);
  }

  private void discoverMarkets() {
    try {
      List<GabagoolMarket> markets = new ArrayList<>();

      List<GabagoolMarketDiscovery.DiscoveredMarket> discovered =
          marketDiscovery.getActiveMarkets();
      for (GabagoolMarketDiscovery.DiscoveredMarket d : discovered) {
        markets.add(
            new GabagoolMarket(
                d.slug(), d.upTokenId(), d.downTokenId(), d.endTime(), d.marketType()));
      }

      GabagoolConfig cfg = getConfig();
      if (cfg.markets() != null) {
        for (GabagoolConfig.GabagoolMarketConfig m : cfg.markets()) {
          if (m.upTokenId() != null && m.downTokenId() != null) {
            Instant endTime =
                m.endTime() != null ? m.endTime() : clock.instant().plus(Duration.ofMinutes(15));
            String upToken = m.upTokenId();
            boolean exists =
                markets.stream().anyMatch(existing -> existing.upTokenId().equals(upToken));
            if (!exists) {
              markets.add(
                  new GabagoolMarket(
                      m.slug() != null ? m.slug() : "configured",
                      m.upTokenId(),
                      m.downTokenId(),
                      endTime,
                      "unknown"));
            }
          }
        }
      }

      Set<String> nextTokens =
          markets.stream()
              .flatMap(m -> Stream.of(m.upTokenId(), m.downTokenId()))
              .collect(java.util.stream.Collectors.toSet());
      for (OrderState old : orderManager.getOpenOrders().values())
        if (!nextTokens.contains(old.tokenId()))
          orderManager.cancelOrder(old.tokenId(), CancelReason.OUTSIDE_LIFETIME, null, null, null);
      activeMarkets.set(markets);
      metricsService.updateActiveMarketsCount(markets.size());
      if (cfg.bankrollUsd() != null) metricsService.updateBankroll(cfg.bankrollUsd());

      List<String> assetIds =
          markets.stream()
              .flatMap(m -> Stream.of(m.upTokenId(), m.downTokenId()))
              .filter(Objects::nonNull)
              .filter(s -> !s.isBlank())
              .distinct()
              .toList();
      if (!assetIds.isEmpty()) marketWs.setSubscribedAssets(assetIds);

      if (!markets.isEmpty()) {
        log.debug(
            "GABAGOOL: Tracking {} markets ({} discovered, {} configured)",
            markets.size(),
            discovered.size(),
            cfg.markets() != null ? cfg.markets().size() : 0);
      }
    } catch (Exception e) {
      log.error("GABAGOOL: Error discovering markets: {}", e.getMessage());
    }
  }

  private GabagoolConfig getConfig() {
    return GabagoolConfig.from(properties.strategy().gabagool());
  }

  private BigDecimal getTickSize(String tokenId) {
    BigDecimal observed = marketWs.observedTickSize(tokenId).orElse(null);
    if (observed != null) return observed;
    TickSizeEntry cached = tickSizeCache.get(tokenId);
    if (cached != null
        && Duration.between(cached.fetchedAt(), clock.instant()).compareTo(TICK_SIZE_CACHE_TTL)
            < 0) {
      return cached.tickSize();
    }
    try {
      BigDecimal tickSize = executorApi.getTickSize(tokenId);
      tickSizeCache.put(tokenId, new TickSizeEntry(tickSize, clock.instant()));
      return tickSize;
    } catch (Exception e) {
      log.warn("Failed to get tick size for {}: {}", tokenId, e.getMessage());
      return null;
    }
  }

  private boolean isStale(TopOfBook tob) {
    if (tob == null || tob.updatedAt() == null) return true;
    return Duration.between(tob.updatedAt(), clock.instant()).toMillis() > 2_000;
  }

  private void logStartupConfig(GabagoolConfig cfg) {
    log.info(
        "gabagool strategy config loaded (enabled={}, refreshMillis={}, quoteSizeUsd={},"
            + " bankrollUsd={})",
        cfg.enabled(),
        cfg.refreshMillis(),
        cfg.quoteSize(),
        cfg.bankrollUsd());
    log.info(
        "Phase-2 coordinated maker pairs active; legacy taker/top-up paths removed; mergeCost={},"
            + " activationMs={}",
        mergeCost,
        activationMs);
  }

  public record TickSizeEntry(BigDecimal tickSize, Instant fetchedAt) {}
}
