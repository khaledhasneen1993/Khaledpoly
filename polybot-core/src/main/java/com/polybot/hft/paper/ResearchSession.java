package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import com.polybot.hft.state.AtomicJsonState;
import java.math.*;
import java.nio.file.Path;
import java.util.*;
import java.util.function.BiConsumer;

/**
 * ONE causal strategy/execution state machine used unchanged by streaming PAPER and closed-loop
 * replay.
 */
public final class ResearchSession implements AutoCloseable {
  private static final BigDecimal ZERO = BigDecimal.ZERO, ONE = BigDecimal.ONE;

  private record Book(
      NavigableMap<BigDecimal, BigDecimal> bids,
      NavigableMap<BigDecimal, BigDecimal> asks,
      long source,
      long received) {}

  private record Pending(
      String condition,
      String token,
      boolean buy,
      BigDecimal quantity,
      BigDecimal limit,
      long due,
      String purpose,
      BigDecimal edge) {}

  public record Checkpoint(
      int version,
      Map<String, ResearchMarket> markets,
      Map<String, Long> unhedged,
      boolean entryStopped,
      BigDecimal exitLossUsed,
      long sequence,
      Set<String> expired,
      Map<String, ResolutionEvidence> resolutions,
      ResearchConfig configuration) {}

  private final AccountLedger ledger;
  private final ResearchConfig cfg;
  private final ObjectMapper mapper;
  private final PaperMatchingEngine matching;
  private final PaperMetrics markouts = new PaperMetrics();
  private final ExperimentMetrics metrics = new ExperimentMetrics();
  private final AtomicJsonState checkpoint;
  private final BiConsumer<String, Object> output;
  private final Map<String, ResearchMarket> markets = new TreeMap<>();
  private final Map<String, Book> books = new HashMap<>();
  private final Map<String, Long> unhedged = new HashMap<>();
  private final Map<String, ResolutionEvidence> resolutions = new HashMap<>();
  private final Set<String> expired = new HashSet<>();
  private final Map<String, BigDecimal> mids = new HashMap<>(), vols = new HashMap<>();
  private final Map<String, Long> quoteAt = new HashMap<>(), lastTakerSource = new HashMap<>();
  private final List<Pending> pending = new ArrayList<>();
  private long now = -1, nextDecision, sequence, inputSequence;
  private final String sessionId = UUID.randomUUID().toString();
  private boolean entryStopped;
  private boolean failed;
  private boolean insideFrame;
  private BigDecimal exitLossUsed = ZERO;
  private int riskBreaches;

  public ResearchSession(
      AccountLedger ledger,
      ResearchConfig cfg,
      ObjectMapper mapper,
      Path state,
      BiConsumer<String, Object> output) {
    this.ledger = ledger;
    this.cfg = cfg;
    this.mapper = mapper;
    this.output = output;
    matching =
        new PaperMatchingEngine(
            cfg.activationMs(), cfg.cancelMs(), cfg.maxBookAgeMs(), cfg.queueMultiplier());
    checkpoint = new AtomicJsonState(state, mapper);
    JsonNode saved = checkpoint.load();
    if (saved != null) {
      var s = mapper.convertValue(saved, Checkpoint.class);
      if (s.version() != 1 || !cfg.equals(s.configuration()))
        throw new IllegalArgumentException("Research configuration changed on existing account");
      markets.putAll(s.markets());
      unhedged.putAll(s.unhedged());
      entryStopped = s.entryStopped();
      exitLossUsed = s.exitLossUsed();
      sequence = s.sequence();
      expired.addAll(s.expired());
      resolutions.putAll(s.resolutions());
    }
    for (String id : ledger.snapshot().orders().keySet())
      if (id.matches("sim-research-[0-9]+"))
        sequence = Math.max(sequence, Long.parseLong(id.substring("sim-research-".length())));
    for (String id : ledger.snapshot().executions()) {
      if (id.matches("session:[0-9]+:.*"))
        sequence = Math.max(sequence, Long.parseLong(id.split(":")[1]));
      if (id.matches("session-merge:[0-9]+"))
        sequence = Math.max(sequence, Long.parseLong(id.substring("session-merge:".length())));
    }
    // No queue, pending taker, or fill is fabricated over downtime.
    ledger.snapshot().orders().keySet().forEach(ledger::cancel);
    for (var e : ledger.snapshot().holdings().entrySet())
      if (e.getValue().shares().signum() > 0
          && markets.values().stream()
              .noneMatch(m -> m.first().equals(e.getKey()) || m.second().equals(e.getKey())))
        entryStopped = true;
    if (ledger.snapshot().holdings().values().stream().anyMatch(h -> h.shares().signum() > 0)) {
      entryStopped = true;
      exitLossUsed = cfg.maxExitLoss();
    }
    for (var m : markets.values())
      if (holding(m.first()).shares().compareTo(holding(m.second()).shares()) != 0
          && !unhedged.containsKey(m.condition())) unhedged.put(m.condition(), 0L);
    save();
  }

  private void save() {
    checkpoint.save(
        new Checkpoint(
            1,
            Map.copyOf(markets),
            Map.copyOf(unhedged),
            entryStopped,
            exitLossUsed,
            sequence,
            Set.copyOf(expired),
            Map.copyOf(resolutions),
            cfg));
  }

  public synchronized List<ResearchMarket> markets() {
    return List.copyOf(markets.values());
  }

  public synchronized Set<String> resolved() {
    return Set.copyOf(resolutions.keySet());
  }

  public synchronized void accept(String kind, long at, JsonNode data) {
    if (failed)
      throw new IllegalStateException("Research session failed; restart/reconciliation required");
    if (at < now) throw new IllegalArgumentException("Causal clock regression");
    now = at;
    if (!insideFrame) inputSequence++;
    if (kind.equals("FRAME")) {
      if (insideFrame || !data.path("events").isArray())
        throw new IllegalArgumentException("Invalid or nested research frame");
      // Validate the envelope before applying anything. No persisted actions/metadata in a frame.
      for (var event : data.path("events"))
        if (!Set.of("BOOK", "TRADE", "TICK_SIZE", "GAP").contains(event.path("kind").asText())
            || !event.path("data").isObject())
          throw new IllegalArgumentException("Invalid research frame event");
      insideFrame = true;
      try {
        for (var event : data.path("events"))
          accept(event.path("kind").asText(), at, event.path("data"));
      } catch (RuntimeException e) {
        failed = true;
        throw e;
      } finally {
        insideFrame = false;
      }
      if (!data.path("events").isEmpty()) advanceActions();
      return;
    }
    if (kind.equals("META")) {
      ResearchMarket m = mapper.convertValue(data, ResearchMarket.class);
      if (m.observedMs() > at) throw new IllegalArgumentException("Future metadata");
      ResearchMarket previous = markets.get(m.condition());
      if (previous != null
          && (!previous.first().equals(m.first())
              || !previous.second().equals(m.second())
              || previous.startMs() != m.startMs()
              || previous.endMs() != m.endMs()))
        throw new IllegalArgumentException("Market identity changed");
      markets.put(m.condition(), m);
      save();
      if (!m.accepting()) {
        closeToken(m.first());
        closeToken(m.second());
      }
    } else if (kind.equals("TICK_SIZE")) {
      long source = data.path("sourceMs").asLong(-1);
      if (source < 0 || source > at || at - source > cfg.maxBookAgeMs())
        throw new IllegalArgumentException("Invalid tick timestamp");
      String token = data.path("token").asText();
      BigDecimal tick = PaperMatchingEngine.decimal(data, "tick");
      if (tick.signum() <= 0 || tick.compareTo(ONE) >= 0)
        throw new IllegalArgumentException("Invalid tick");
      for (var m : List.copyOf(markets.values()))
        if (m.first().equals(token) || m.second().equals(token)) {
          markets.put(
              m.condition(),
              new ResearchMarket(
                  m.condition(),
                  m.first(),
                  m.second(),
                  m.startMs(),
                  m.endMs(),
                  m.tick().max(tick),
                  m.minSize(),
                  m.feeRate(),
                  m.feeExponent(),
                  m.accepting(),
                  m.observedMs(),
                  m.evidence()));
          cancelAll(m);
        }
      save();
    } else if (kind.equals("RESOLUTION")) {
      String condition = PaperMatchingEngine.required(data, "condition_id");
      ResearchMarket m = markets.get(condition);
      if (m == null)
        throw new IllegalArgumentException("Resolution without prior token-slot metadata");
      ResolutionEvidence evidence = ResolutionEvidence.parse(m, data, at);
      ResolutionEvidence prior = resolutions.get(condition);
      if (prior != null && !prior.payouts().equals(evidence.payouts()))
        throw new IllegalStateException("Conflicting terminal payouts");
      if (prior == null) {
        closeToken(m.first());
        closeToken(m.second());
        BigDecimal quantity = holding(m.first()).shares().add(holding(m.second()).shares());
        BigDecimal cost = quantity.signum() > 0 ? cfg.redemptionCost() : ZERO;
        ledger.redeem("resolution:" + condition, evidence.payouts(), cost);
        resolutions.put(condition, evidence);
        unhedged.remove(condition);
        pending.removeIf(p -> p.condition().equals(condition));
        save();
        output.accept("RESOLVED", evidence);
      }
    } else if (Set.of("BOOK", "TRADE", "GAP", "TICK").contains(kind)) {
      if (kind.equals("TRADE")) {
        String token = data.path("token").asText();
        if (markets.values().stream()
            .anyMatch(
                m -> (m.first().equals(token) || m.second().equals(token)) && at >= m.endMs()))
          kind = "TICK";
      }
      apply(matching.accept(kind, at, data));
      if (kind.equals("BOOK")) {
        long source = data.path("sourceMs").asLong(-1);
        String token = data.path("token").asText();
        Book prior = books.get(token);
        if (source < 0
            || source > at
            || at - source > cfg.maxBookAgeMs()
            || prior != null && source < prior.source()) books.remove(token);
        else {
          Book b = new Book(levels(data.path("bids")), levels(data.path("asks")), source, at);
          books.put(token, b);
          markouts.book(data, at);
          if (!b.bids.isEmpty() && !b.asks.isEmpty()) {
            BigDecimal mid = b.bids.lastKey().add(b.asks.firstKey()).divide(BigDecimal.valueOf(2));
            BigDecimal old = mids.put(token, mid);
            if (old != null)
              vols.merge(
                  token,
                  mid.subtract(old).abs(),
                  (a, v) ->
                      a.multiply(new BigDecimal("0.9")).add(v.multiply(new BigDecimal("0.1"))));
          }
        }
      }
      if (kind.equals("GAP")) {
        books.clear();
        pending.clear();
        output.accept(
            "ALERT",
            Map.of(
                "key",
                "data-gap",
                "at",
                now,
                "message",
                "Depth invalidated; resting orders canceled"));
      }
    } else if (kind.equals("MARKET_UNAVAILABLE")) {
      // Disable only the affected known market; never refresh its metadata freshness clock.
      ResearchMarket m = markets.get(data.path("condition").asText());
      if (m != null) {
        markets.put(
            m.condition(),
            new ResearchMarket(
                m.condition(),
                m.first(),
                m.second(),
                m.startMs(),
                m.endMs(),
                m.tick(),
                m.minSize(),
                m.feeRate(),
                m.feeExponent(),
                false,
                m.observedMs(),
                m.evidence()));
        cancelAll(m);
        pending.removeIf(p -> p.condition().equals(m.condition()));
        save();
      }
      output.accept("MARKET_UNAVAILABLE", data);
    } else throw new IllegalArgumentException("Unknown research input " + kind);
    if (!insideFrame) advanceActions();
  }

  private void advanceActions() {
    expire();
    executePending();
    merge();
    trackRisk();
    mark();
    if (now >= nextDecision) {
      nextDecision = now + cfg.decisionMillis();
      decide();
    }
  }

  private void apply(PaperMatchingEngine.Update update) {
    for (var f : update.fills()) {
      BigDecimal saleLoss =
          f.buy()
              ? ZERO
              : holding(f.token())
                  .basis()
                  .multiply(f.size())
                  .divide(holding(f.token()).shares(), 18, RoundingMode.HALF_EVEN)
                  .subtract(f.price().multiply(f.size()))
                  .max(ZERO);
      exitLossUsed = exitLossUsed.add(saleLoss);
      ledger.fill("session:" + (++sequence) + ":" + f.id(), f.id(), f.size(), f.price(), ZERO);
      markouts.fill(f);
      metrics.fill(f, ZERO, "MAKER");
      output.accept("FILL", f);
    }
    if (!update.fills().isEmpty()) save();
    update
        .terminal()
        .forEach(
            (id, status) -> {
              if (!status.equals("FILLED")) ledger.cancel(id);
              output.accept("ORDER_TERMINAL", Map.of("id", id, "status", status, "at", now));
            });
  }

  private void closeToken(String token) {
    apply(matching.accept("CLOSE", now, node(Map.of("token", token))));
    books.remove(token);
    pending.removeIf(p -> p.token.equals(token));
  }

  private void expire() {
    for (var m : markets.values())
      if (now >= m.endMs() && expired.add(m.condition())) {
        metrics.expiry(holding(m.first()).shares().subtract(holding(m.second()).shares()).abs());
        closeToken(m.first());
        closeToken(m.second());
        save();
      }
  }

  private void mark() {
    var marks = new HashMap<String, BigDecimal>();
    BigDecimal equity = ledger.snapshot().cash();
    boolean fresh = true;
    for (var e : ledger.snapshot().holdings().entrySet())
      if (e.getValue().shares().signum() > 0) {
        Book b = books.get(e.getKey());
        if (!fresh(b) || b.bids.isEmpty()) {
          fresh = false;
          continue;
        }
        marks.put(e.getKey(), b.bids.lastKey());
        equity = equity.add(e.getValue().shares().multiply(b.bids.lastKey()));
      }
    metrics.equity(equity, fresh);
    if (fresh) {
      ledger.mark(marks);
      if (ledger.snapshot().halted()) {
        entryStopped = true;
        cancelAll(null);
        save();
      }
    }
  }

  private void merge() {
    for (var m : markets.values()) {
      BigDecimal q = availableShares(m.first()).min(availableShares(m.second()));
      if (q.compareTo(cfg.mergeCost()) <= 0) continue;
      BigDecimal before = ledger.snapshot().realized();
      ledger.merge("session-merge:" + (++sequence), m.first(), m.second(), q, cfg.mergeCost());
      metrics.merge(m.condition(), now, q, ledger.snapshot().realized().subtract(before));
      output.accept(
          "MERGE",
          Map.of("condition", m.condition(), "quantity", q, "cost", cfg.mergeCost(), "at", now));
      save();
    }
  }

  private void trackRisk() {
    boolean changed = false;
    for (var m : markets.values()) {
      BigDecimal q = holding(m.first()).shares().subtract(holding(m.second()).shares()).abs();
      if (q.signum() == 0) {
        changed |= unhedged.remove(m.condition()) != null;
        continue;
      }
      if (!unhedged.containsKey(m.condition())) {
        unhedged.put(m.condition(), now);
        changed = true;
      }
      if (now - unhedged.get(m.condition()) >= cfg.unhedgedMs()
          || q.compareTo(cfg.maxUnhedged()) >= 0) {
        if (!entryStopped) {
          entryStopped = true;
          changed = true;
          if (q.compareTo(cfg.maxUnhedged()) > 0) riskBreaches++;
        }
        output.accept(
            "ALERT",
            Map.of(
                "key",
                "unhedged:" + m.condition(),
                "at",
                now,
                "message",
                "Unhedged inventory requires bounded risk reduction"));
      }
    }
    if (changed) save();
  }

  private void decide() {
    List<ResearchMarket> ranked =
        markets.values().stream()
            .sorted(Comparator.comparing(this::cost).thenComparing(ResearchMarket::condition))
            .toList();
    for (var m : ranked) {
      if (resolutions.containsKey(m.condition())
          || now < m.startMs()
          || now >= m.endMs()
          || !m.accepting()) {
        metrics.decision("OUTSIDE_MARKET", null);
        continue;
      }
      Book a = books.get(m.first()), b = books.get(m.second());
      String unavailable =
          a == null || b == null
              ? "BOOK_MISSING"
              : !fresh(a) || !fresh(b)
                  ? "BOOK_STALE"
                  : a.bids.isEmpty() || a.asks.isEmpty() || b.bids.isEmpty() || b.asks.isEmpty()
                      ? "EMPTY_DEPTH"
                      : now - m.observedMs() > cfg.metadataMaxAgeMs() ? "METADATA_STALE" : null;
      if (unavailable != null) {
        cancelAll(m);
        metrics.decision(unavailable, null);
        continue;
      }
      BigDecimal imbalance = holding(m.first()).shares().subtract(holding(m.second()).shares());
      if (imbalance.signum() != 0) {
        reduce(m, imbalance, a, b);
        continue;
      }
      if (entryStopped || ledger.snapshot().halted()) {
        cancelAll(m);
        metrics.decision("ENTRY_SUSPENDED", null);
        continue;
      }
      if (a.source <= lastTakerSource.getOrDefault(m.first(), -1L)
          || b.source <= lastTakerSource.getOrDefault(m.second(), -1L)) {
        metrics.decision("WAIT_NEW_DEPTH", null);
        continue;
      }
      BigDecimal ap = bid(a, m.tick()),
          bp = bid(b, m.tick()),
          depth = a.bids.lastEntry().getValue().min(b.bids.lastEntry().getValue());
      BigDecimal q =
          cfg.orderShares()
              .min(depth.multiply(new BigDecimal("0.1")))
              .setScale(2, RoundingMode.DOWN);
      if (ap.compareTo(m.tick()) < 0
          || bp.compareTo(m.tick()) < 0
          || ap.compareTo(ONE.subtract(m.tick())) > 0
          || bp.compareTo(ONE.subtract(m.tick())) > 0) {
        cancelAll(m);
        metrics.decision("PRICE_BOUND_OR_STALE_TICK", null);
        continue;
      }
      BigDecimal edge = ONE.subtract(ap).subtract(bp),
          required =
              PairPolicy.requiredEdge(
                  cfg.minimumEdge(),
                  vols.getOrDefault(m.first(), ZERO),
                  (m.endMs() - now) / 1000,
                  depth,
                  cfg.activationMs(),
                  ZERO);
      boolean small = q.compareTo(m.minSize()) < 0;
      boolean insufficientEdge =
          edge.multiply(q).subtract(cfg.mergeCost()).compareTo(required.multiply(q)) < 0;
      if (small || insufficientEdge) {
        cancelAll(m);
        metrics.decision(
            small && insufficientEdge ? "MIN_SIZE_AND_NET_EDGE" : small ? "MIN_SIZE" : "NET_EDGE",
            edge);
        continue;
      }
      List<String> open = open(m);
      if (!open.isEmpty()) {
        boolean same =
            open.size() == 2
                && open.stream()
                    .allMatch(
                        id -> {
                          var o = ledger.snapshot().orders().get(id);
                          return o.buy()
                              && o.price().compareTo(o.token().equals(m.first()) ? ap : bp) == 0;
                        });
        if (!same && now - quoteAt.getOrDefault(m.condition(), now) >= 2000) cancelAll(m);
        metrics.decision("RESTING", edge);
        continue;
      }
      BigDecimal value = ap.add(bp).multiply(q);
      if (value.compareTo(ledger.availableCash()) > 0
          || gross().add(value).compareTo(cfg.portfolioBudget()) > 0) {
        metrics.decision("BUDGET", edge);
        continue;
      }
      String ai = id(), bi = id();
      try {
        ledger.reservePair(ai, m.first(), bi, m.second(), ap, bp, q);
      } catch (IllegalStateException e) {
        if (ledger.persistenceFailed()) throw e;
        metrics.decision("RISK_REJECTION", edge);
        continue;
      }
      submit(ai, m, m.first(), true, ap, q, edge, "ENTRY");
      submit(bi, m, m.second(), true, bp, q, edge, "ENTRY");
      quoteAt.put(m.condition(), now);
      metrics.decision("PAIR_SUBMITTED", edge);
      save();
    }
  }

  private void reduce(ResearchMarket m, BigDecimal imbalance, Book a, Book b) {
    long age = now - unhedged.getOrDefault(m.condition(), now);
    boolean overdue = age >= cfg.unhedgedMs() || imbalance.abs().compareTo(cfg.maxUnhedged()) >= 0;
    if (age < 5000 && !overdue) {
      metrics.decision("WAIT_SECOND_LEG", null);
      return;
    }
    if (!open(m).isEmpty()) {
      boolean sellsOnly =
          open(m).stream().allMatch(id -> !ledger.snapshot().orders().get(id).buy());
      if (sellsOnly && !overdue) {
        metrics.decision("RESTING_REDUCTION", null);
        return;
      }
      cancelAll(m);
      metrics.decision("CANCEL_BEFORE_EXIT", null);
      return;
    }
    if (pending.stream().anyMatch(p -> p.condition.equals(m.condition()))) return;
    String lead = imbalance.signum() > 0 ? m.first() : m.second(),
        other = imbalance.signum() > 0 ? m.second() : m.first();
    Book lb = imbalance.signum() > 0 ? a : b, ob = imbalance.signum() > 0 ? b : a;
    BigDecimal quantity = imbalance.abs(),
        basis = holding(lead).basis().divide(holding(lead).shares(), 18, RoundingMode.HALF_EVEN);
    FeeModel fee = new FeeModel(m.feeRate().multiply(cfg.feeMultiplier()), m.feeExponent());
    var choice =
        PairPolicy.hedge(
            basis,
            ob.asks.firstKey(),
            lb.bids.lastKey(),
            fee.fee(ONE, ob.asks.firstKey(), false)
                .add(cfg.mergeCost().divide(quantity, 18, RoundingMode.UP)),
            fee.fee(ONE, lb.bids.lastKey(), false),
            cfg.minimumEdge(),
            overdue);
    output.accept(
        "HEDGE_DECISION", Map.of("condition", m.condition(), "choice", choice, "at", now));
    if (!overdue && !choice.action().equals("COMPLETE")) {
      BigDecimal price = lb.asks.firstKey().subtract(m.tick()).max(lb.bids.lastKey().add(m.tick()));
      if (price.compareTo(ONE) >= 0 || quantity.compareTo(m.minSize()) < 0) return;
      if (price.subtract(basis).multiply(quantity).negate().max(ZERO).compareTo(exitLossAvailable())
          > 0) {
        metrics.decision("EXIT_LOSS_CAP", null);
        return;
      }
      String id = id();
      ledger.reserveRiskSale(id, lead, price, quantity);
      submit(id, m, lead, false, price, quantity, price.subtract(basis), "MAKER_REDUCTION");
      save();
      return;
    }
    boolean buy = choice.action().endsWith("COMPLETE") && !ledger.snapshot().halted();
    String token = buy ? other : lead;
    Book bk = buy ? ob : lb;
    BigDecimal limit =
        buy
            ? bk.asks
                .firstKey()
                .add(m.tick().multiply(BigDecimal.valueOf(3)))
                .min(ONE.subtract(m.tick()))
            : bk.bids.lastKey().subtract(m.tick().multiply(BigDecimal.valueOf(3))).max(m.tick());
    pending.add(
        new Pending(
            m.condition(),
            token,
            buy,
            quantity,
            limit,
            now + cfg.activationMs(),
            overdue ? "RISK_REDUCTION" : "POSITIVE_EDGE_COMPLETION",
            choice.completeValue()));
    metrics.decision("TAKER_PENDING", null);
  }

  private void executePending() {
    var due = pending.stream().filter(p -> p.due <= now).toList();
    pending.removeAll(due);
    for (var p : due) {
      ResearchMarket m = markets.get(p.condition);
      Book b = books.get(p.token);
      if (m == null
          || resolutions.containsKey(m.condition())
          || now >= m.endMs()
          || !fresh(b)
          || now - m.observedMs() > cfg.metadataMaxAgeMs()
          || b.source <= lastTakerSource.getOrDefault(p.token, -1L)) {
        metrics.decision("TAKER_DATA_REJECT", null);
        continue;
      }
      if (!open(m).isEmpty()) continue;
      BigDecimal imbalance = holding(m.first()).shares().subtract(holding(m.second()).shares());
      String lead = imbalance.signum() > 0 ? m.first() : m.second();
      if (imbalance.signum() == 0) continue;
      BigDecimal q = p.quantity.min(imbalance.abs());
      if (q.compareTo(m.minSize()) < 0) {
        metrics.decision("DUST_AWAIT_RESOLUTION", null);
        continue;
      }
      DepthExecution.Result result;
      try {
        result =
            DepthExecution.sweep(
                p.buy ? b.asks : b.bids,
                p.buy,
                q,
                p.limit,
                new FeeModel(m.feeRate().multiply(cfg.feeMultiplier()), m.feeExponent()));
      } catch (IllegalStateException e) {
        metrics.decision("TAKER_FOK_REJECT", null);
        continue;
      }
      BigDecimal basis =
          holding(lead)
              .basis()
              .multiply(q)
              .divide(holding(lead).shares(), 18, RoundingMode.HALF_EVEN);
      BigDecimal pnl =
          p.buy
              ? q.subtract(basis)
                  .subtract(result.notional())
                  .subtract(result.fee())
                  .subtract(cfg.mergeCost())
              : result.notional().subtract(result.fee()).subtract(basis);
      if (p.purpose.equals("POSITIVE_EDGE_COMPLETION")
          && pnl.compareTo(cfg.minimumEdge().multiply(q)) < 0) {
        metrics.decision("TAKER_NET_EDGE", pnl);
        continue;
      }
      BigDecimal loss = pnl.negate().max(ZERO);
      if (loss.compareTo(exitLossAvailable()) > 0) {
        metrics.decision("EXIT_LOSS_CAP", pnl);
        continue;
      }
      if (p.buy
          && (ledger.snapshot().halted()
              || p.limit.multiply(q).add(result.fee()).compareTo(ledger.availableCash()) > 0))
        continue;
      String id = id();
      if (p.buy) ledger.reserve(id, p.token, true, p.limit, q);
      else ledger.reserveRiskSale(id, p.token, p.limit, q);
      metrics.intent(id, now, m.condition(), pnl.divide(q, 12, RoundingMode.HALF_EVEN), p.purpose);
      int part = 0;
      for (var leg : result.legs()) {
        ledger.fill("taker:" + id + ":" + (++part), id, leg.size(), leg.price(), leg.fee());
        var f = new PaperMatchingEngine.Fill(id, p.token, p.buy, leg.price(), leg.size(), now);
        metrics.fill(f, leg.fee(), "TAKER");
        markouts.fill(f);
        output.accept("TAKER_FILL", Map.of("fill", f, "fee", leg.fee(), "purpose", p.purpose));
      }
      exitLossUsed = exitLossUsed.add(loss);
      lastTakerSource.put(p.token, b.source);
      save();
    }
  }

  private BigDecimal exitLossAvailable() {
    BigDecimal reserved = ZERO;
    for (var o : ledger.snapshot().orders().values())
      if (!o.buy() && o.remaining().signum() > 0) {
        var h = holding(o.token());
        if (h.shares().signum() > 0)
          reserved =
              reserved.add(
                  h.basis()
                      .divide(h.shares(), 18, RoundingMode.HALF_EVEN)
                      .subtract(o.price())
                      .max(ZERO)
                      .multiply(o.remaining()));
      }
    return cfg.maxExitLoss().subtract(exitLossUsed).subtract(reserved).max(ZERO);
  }

  private void submit(
      String id,
      ResearchMarket m,
      String token,
      boolean buy,
      BigDecimal price,
      BigDecimal q,
      BigDecimal edge,
      String purpose) {
    metrics.intent(id, now, m.condition(), edge, purpose);
    apply(
        matching.accept(
            "ORDER",
            now,
            node(
                Map.of(
                    "id",
                    id,
                    "token",
                    token,
                    "side",
                    buy ? "BUY" : "SELL",
                    "price",
                    price,
                    "size",
                    q))));
    output.accept(
        "ORDER",
        Map.of(
            "id",
            id,
            "condition",
            m.condition(),
            "price",
            price,
            "quantity",
            q,
            "purpose",
            purpose,
            "at",
            now));
  }

  public synchronized void cancel(String id) {
    apply(matching.accept("CANCEL", now, node(Map.of("id", id))));
  }

  private void cancelAll(ResearchMarket m) {
    for (String id : open(m)) cancel(id);
  }

  private List<String> open(ResearchMarket m) {
    return ledger.snapshot().orders().entrySet().stream()
        .filter(
            e ->
                e.getValue().remaining().signum() > 0
                    && (m == null
                        || e.getValue().token().equals(m.first())
                        || e.getValue().token().equals(m.second())))
        .map(Map.Entry::getKey)
        .sorted()
        .toList();
  }

  private AccountLedger.Holding holding(String t) {
    return ledger.snapshot().holdings().getOrDefault(t, new AccountLedger.Holding(ZERO, ZERO));
  }

  private BigDecimal availableShares(String t) {
    BigDecimal reserved =
        ledger.snapshot().orders().values().stream()
            .filter(o -> !o.buy() && o.token().equals(t))
            .map(AccountLedger.Reservation::remaining)
            .reduce(ZERO, BigDecimal::add);
    return holding(t).shares().subtract(reserved);
  }

  private BigDecimal gross() {
    return ledger.snapshot().holdings().values().stream()
        .map(AccountLedger.Holding::basis)
        .reduce(ZERO, BigDecimal::add)
        .add(
            ledger.snapshot().orders().values().stream()
                .filter(AccountLedger.Reservation::buy)
                .map(o -> o.price().multiply(o.remaining()))
                .reduce(ZERO, BigDecimal::add));
  }

  private boolean fresh(Book b) {
    return b != null && b.source <= now && now - b.source <= cfg.maxBookAgeMs();
  }

  private BigDecimal bid(Book b, BigDecimal tick) {
    return b.bids
        .lastKey()
        .add(tick)
        .min(b.asks.firstKey().subtract(tick))
        .divide(tick, 0, RoundingMode.FLOOR)
        .multiply(tick);
  }

  private BigDecimal cost(ResearchMarket m) {
    Book a = books.get(m.first()), b = books.get(m.second());
    return !fresh(a) || !fresh(b) || a.bids.isEmpty() || b.bids.isEmpty()
        ? BigDecimal.TEN
        : a.bids.lastKey().add(b.bids.lastKey());
  }

  private String id() {
    return "sim-research-" + (++sequence);
  }

  private JsonNode node(Object o) {
    return mapper.valueToTree(o);
  }

  private static NavigableMap<BigDecimal, BigDecimal> levels(JsonNode n) {
    var map = new TreeMap<BigDecimal, BigDecimal>();
    for (var r : n) {
      var size = PaperMatchingEngine.decimal(r, "size");
      if (size.signum() > 0) map.put(PaperMatchingEngine.decimal(r, "price"), size);
    }
    return map;
  }

  /** A detached, bounded observation. This method never submits or cancels an order. */
  public synchronized JsonNode researchSnapshot(long generatedAt) {
    if (now < 0 || generatedAt < now) throw new IllegalStateException("No causal observation");
    var state = ledger.snapshot();
    var account = new LinkedHashMap<String, Object>();
    account.put("id", "paper-default");
    account.put("cash", state.cash());
    account.put("availableCash", ledger.availableCash());
    account.put("realizedPnl", state.realized());
    account.put("fees", state.fees());
    account.put("halted", failed || entryStopped || state.halted());
    account.put("pendingTakers", pending.size());
    var holdings = new TreeMap<String, AccountLedger.Holding>();
    state
        .holdings()
        .forEach(
            (token, h) -> {
              if (h.shares().signum() > 0) holdings.put(token, h);
            });
    var orders = new TreeMap<String, AccountLedger.Reservation>();
    state
        .orders()
        .forEach(
            (id, o) -> {
              if (o.remaining().signum() > 0) orders.put(id, o);
            });
    if (holdings.size() > 4096 || orders.size() > 4096)
      throw new IllegalStateException("Research account observation exceeds bounds");
    account.put("holdings", holdings);
    account.put("orders", orders);
    var relevant =
        markets.values().stream()
            .filter(
                m ->
                    m.endMs() > generatedAt
                        || holding(m.first()).shares().signum() > 0
                        || holding(m.second()).shares().signum() > 0
                        || state.orders().values().stream()
                            .anyMatch(
                                o ->
                                    o.remaining().signum() > 0
                                        && (o.token().equals(m.first())
                                            || o.token().equals(m.second()))))
            .toList();
    var depth = new TreeMap<String, Object>();
    books.entrySet().stream()
        .sorted(Map.Entry.comparingByKey())
        .limit(512)
        .forEach(
            e -> {
              var b = e.getValue();
              depth.put(
                  e.getKey(),
                  Map.of(
                      "sourceMs",
                      b.source(),
                      "receivedMs",
                      b.received(),
                      "bids",
                      researchLevels(b.bids().descendingMap()),
                      "asks",
                      researchLevels(b.asks()),
                      "depthTruncated",
                      b.bids().size() > 50 || b.asks().size() > 50));
            });
    var result = new LinkedHashMap<String, Object>();
    result.put("schema", 1);
    result.put("mode", "PAPER");
    result.put("researchOnly", true);
    result.put("executionEnabled", false);
    result.put("liveAllowed", false);
    result.put("sessionId", sessionId);
    result.put("sequence", inputSequence);
    result.put("inputMs", now);
    result.put("generatedMs", generatedAt);
    result.put("maxBookAgeMs", cfg.maxBookAgeMs());
    result.put("metadataMaxAgeMs", cfg.metadataMaxAgeMs());
    result.put("account", account);
    result.put("markets", relevant.stream().limit(256).toList());
    result.put("books", depth);
    result.put("truncated", relevant.size() > 256 || books.size() > 512);
    return mapper.valueToTree(result);
  }

  private List<Map<String, BigDecimal>> researchLevels(NavigableMap<BigDecimal, BigDecimal> side) {
    return side.entrySet().stream()
        .limit(50)
        .map(e -> Map.of("price", e.getKey(), "size", e.getValue()))
        .toList();
  }

  public synchronized Map<String, Object> report() {
    var r = new LinkedHashMap<String, Object>(metrics.report());
    r.putAll(markouts.snapshot(Math.max(now, 0)));
    r.put("cash", ledger.snapshot().cash());
    r.put("availableCash", ledger.availableCash());
    r.put("netRealizedPnl", ledger.snapshot().realized());
    r.put("feesAndSettlementCosts", ledger.snapshot().fees());
    r.put("holdings", ledger.snapshot().holdings());
    r.put("halted", entryStopped || ledger.snapshot().halted());
    r.put("dataGaps", matching.gaps());
    r.put("riskBreaches", riskBreaches);
    r.put("resolvedMarkets", resolutions.size());
    r.put("resolvedTradedMarkets", metrics.resolvedTraded(resolutions.keySet()));
    r.put("pendingTakers", pending.size());
    r.put("openOrderCount", open(null).size());
    r.put("exitLossUsed", exitLossUsed);
    r.put("decision", "NO_GO");
    r.put("configuration", cfg);
    return r;
  }

  public synchronized void suspend() {
    failed = true;
    entryStopped = true;
    pending.clear();
    apply(matching.accept("GAP", Math.max(now, 0), mapper.createObjectNode()));
    ledger.halt();
    save();
  }

  public synchronized void close() {
    save();
    checkpoint.close();
  }
}
