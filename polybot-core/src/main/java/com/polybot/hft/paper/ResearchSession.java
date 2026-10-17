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
      ResearchConfig configuration,
      boolean externalMode,
      Map<String, JsonNode> outcomeGroups,
      Map<String, String> groupProofs) {}

  private final AccountLedger ledger;
  private final ResearchConfig cfg;
  private final ObjectMapper mapper;
  private final PaperMatchingEngine matching;
  private final PaperMetrics markouts;
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
  private final String sessionId;
  private final boolean externalMode;
  private final ResearchProposalInbox externalValidator;
  private final LinkedHashMap<Long, Long> observations = new LinkedHashMap<>();
  private final LinkedHashMap<String, JsonNode> externalReplies = new LinkedHashMap<>();
  private final Map<String, Long> externalCancelAt = new HashMap<>();
  private final Map<String, JsonNode> outcomeGroups = new TreeMap<>();
  private final Map<String, String> groupProofs = new TreeMap<>();
  private final Set<String> cancelRequested = new HashSet<>();
  private final Map<String, Long> riskAlertAt = new HashMap<>();
  private boolean haltAlerted;
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
    this(ledger, cfg, mapper, state, output, false, null);
  }

  public ResearchSession(
      AccountLedger ledger,
      ResearchConfig cfg,
      ObjectMapper mapper,
      Path state,
      BiConsumer<String, Object> output,
      boolean externalMode,
      String replaySessionId) {
    this.externalMode = externalMode;
    this.sessionId = replaySessionId == null ? UUID.randomUUID().toString() : replaySessionId;
    externalValidator =
        externalMode
            ? new ResearchProposalInbox(mapper, Path.of(state + ".external-validator"))
            : null;
    this.ledger = ledger;
    this.cfg = cfg;
    this.mapper = mapper;
    this.output = output;
    markouts =
        new PaperMetrics(
            row -> {
              if (externalMode) output.accept("MARKOUT", row);
            });
    matching =
        new PaperMatchingEngine(
            cfg.activationMs(),
            cfg.cancelMs(),
            cfg.maxBookAgeMs(),
            cfg.queueMultiplier(),
            cfg.latencyJitterMs(),
            cfg.latencySeed());
    checkpoint = new AtomicJsonState(state, mapper);
    JsonNode saved = checkpoint.load();
    if (saved != null) {
      var s = mapper.convertValue(saved, Checkpoint.class);
      if (s.version() != 1 || !cfg.equals(s.configuration()) || externalMode != s.externalMode())
        throw new IllegalArgumentException("Research configuration changed on existing account");
      markets.putAll(s.markets());
      if (s.outcomeGroups() != null) outcomeGroups.putAll(s.outcomeGroups());
      if (s.groupProofs() != null) groupProofs.putAll(s.groupProofs());
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
    if (externalMode)
      output.accept(
          "EXTERNAL_CONFIG",
          Map.of(
              "sessionId",
              sessionId,
              "mode",
              "PAPER_EXTERNAL",
              "initialCheckpoint",
              currentCheckpoint(),
              "initialAccount",
              ledger.snapshot()));
  }

  private void save() {
    checkpoint.save(currentCheckpoint());
  }

  private Checkpoint currentCheckpoint() {
    return new Checkpoint(
        1,
        Map.copyOf(markets),
        Map.copyOf(unhedged),
        entryStopped,
        exitLossUsed,
        sequence,
        Set.copyOf(expired),
        Map.copyOf(resolutions),
        cfg,
        externalMode,
        Map.copyOf(outcomeGroups),
        Map.copyOf(groupProofs));
  }

  public synchronized List<ResearchMarket> markets() {
    return List.copyOf(markets.values());
  }

  public synchronized List<JsonNode> outcomeGroups() {
    return outcomeGroups.values().stream().map(n -> (JsonNode) n.deepCopy()).toList();
  }

  public synchronized Set<String> resolved() {
    return Set.copyOf(resolutions.keySet());
  }

  public synchronized void accept(String kind, long at, JsonNode data) {
    if (failed)
      throw new IllegalStateException("Research session failed; restart/reconciliation required");
    if (at < now) throw new IllegalArgumentException("Causal clock regression");
    now = at;
    if (kind.equals("EXTERNAL_PROPOSAL")) {
      if (!externalMode || insideFrame)
        throw new IllegalArgumentException("External PAPER mode required");
      apply(matching.accept("TICK", at, mapper.createObjectNode()));
      processExternal(data);
      inputSequence++;
      advanceActions();
      return;
    }
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
    if (kind.equals("GROUP_META")) {
      if (!externalMode
          || !data.path("id").asText().matches("[0-9]{1,24}")
          || !data.path("negRisk").asBoolean()
          || data.path("negRiskAugmented").asBoolean(false)
          || data.path("markets").size() < 2
          || data.path("markets").size() > 16)
        throw new IllegalArgumentException("Unsupported outcome group metadata");
      if (outcomeGroups.size() >= 32 && !outcomeGroups.containsKey(data.path("id").asText()))
        throw new IllegalStateException("Outcome group bound exceeded");
      outcomeGroups.put(data.path("id").asText(), data.deepCopy());
      save();
    } else if (kind.equals("GROUP_SETTLEMENT")) {
      if (!externalMode)
        throw new IllegalArgumentException("External PAPER group settlement required");
      processGroupSettlement(data);
    } else if (kind.equals("META")) {
      ResearchMarket m = mapper.convertValue(data, ResearchMarket.class);
      if (m.observedMs() > at) throw new IllegalArgumentException("Future metadata");
      ResearchMarket previous = markets.get(m.condition());
      if (previous != null
          && (!previous.first().equals(m.first())
              || !previous.second().equals(m.second())
              || previous.startMs() != m.startMs()
              || previous.endMs() != m.endMs()
              || previous.negativeRisk() != m.negativeRisk()))
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
                  m.evidence(),
                  m.negativeRisk()));
          cancelAll(m, "TICK_SIZE_CHANGED");
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
        if (!externalMode || !m.negativeRisk())
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
      if (kind.equals("GAP")) data = scopedGap(data);
      long gapsBefore = matching.gaps();
      apply(matching.accept(kind, at, data));
      if (matching.gaps() > gapsBefore && !kind.equals("GAP"))
        output.accept(
            "ALERT",
            Map.of(
                "key",
                "stale-depth",
                "at",
                now,
                "message",
                "Stale depth invalidated resting orders; fresh snapshots required"));
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
                      a.multiply(new BigDecimal("0.9"))
                          .add(v.multiply(new BigDecimal("0.1")))
                          .setScale(18, RoundingMode.HALF_EVEN));
          }
        }
      }
      if (kind.equals("GAP")) {
        Set<String> affected = DataGap.tokens(data);
        if (affected.isEmpty()) { books.clear(); pending.clear(); }
        else {
          books.keySet().removeAll(affected);
          pending.removeIf(p -> affected.contains(p.token()));
        }
        output.accept(
            "ALERT",
            Map.of(
                "key",
                "data-gap",
                "at",
                now,
                "message",
                "Affected depth invalidated; affected resting orders canceled"));
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
                m.evidence(),
                m.negativeRisk()));
        cancelAll(m, "MARKET_UNAVAILABLE");
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
      if (!externalMode) decide();
      else {
        for (var market : markets.values())
          if (now < market.endMs()
              && unhedged.containsKey(market.condition())
              && now - unhedged.get(market.condition()) >= cfg.unhedgedMs()) {
            Book a = books.get(market.first()), b = books.get(market.second());
            if (a != null
                && b != null
                && fresh(a)
                && fresh(b)
                && !a.bids.isEmpty()
                && !a.asks.isEmpty()
                && !b.bids.isEmpty()
                && !b.asks.isEmpty())
              reduce(
                  market,
                  holding(market.first()).shares().subtract(holding(market.second()).shares()),
                  a,
                  b);
          }
        for (var e : List.copyOf(externalCancelAt.entrySet()))
          if (now >= e.getValue()) {
            cancel(e.getKey());
            externalCancelAt.remove(e.getKey());
          }
      }
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
              cancelRequested.remove(id);
              metrics.terminal(status, update.reasons().getOrDefault(id, "UNSPECIFIED_LEGACY_TERMINAL"));
              output.accept("ORDER_TERMINAL", Map.of("id", id, "status", status, "at", now,
                  "reason", update.reasons().getOrDefault(id, "UNSPECIFIED_LEGACY_TERMINAL")));
            });
    for (var terminal : update.terminal().entrySet()) {
      if (!terminal.getValue().equals("REJECTED")) continue;
      var rejected = ledger.snapshot().orders().get(terminal.getKey());
      if (rejected == null) continue;
      for (var market : markets.values())
        if (market.first().equals(rejected.token()) || market.second().equals(rejected.token()))
          for (String peer : open(market))
            if (ledger.snapshot().orders().get(peer).buy())
              cancel(peer, "PEER_REJECTED:" + terminal.getKey());
    }
  }

  private void closeToken(String token) {
    apply(matching.accept("CLOSE", now, node(Map.of("token", token, "reason", "MARKET_CLOSED_OR_RESOLVED"))));
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
        if (!haltAlerted) {
          haltAlerted = true;
          output.accept(
              "ALERT",
              Map.of(
                  "key",
                  "risk-halt",
                  "at",
                  now,
                  "message",
                  "Account risk stop; new entries blocked and orders canceled"));
        }
        cancelAll(null, "ACCOUNT_RISK_HALT");
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
        riskAlertAt.remove(m.condition());
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
        if (now - riskAlertAt.getOrDefault(m.condition(), -60000L) >= 60000) {
          riskAlertAt.put(m.condition(), now);
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
        cancelAll(m, unavailable);
        metrics.decision(unavailable, null);
        continue;
      }
      BigDecimal imbalance = holding(m.first()).shares().subtract(holding(m.second()).shares());
      if (imbalance.signum() != 0) {
        reduce(m, imbalance, a, b);
        continue;
      }
      if (entryStopped || ledger.snapshot().halted()) {
        cancelAll(m, "ENTRY_SUSPENDED");
        metrics.decision("ENTRY_SUSPENDED", null);
        continue;
      }
      if (a.source <= lastTakerSource.getOrDefault(m.first(), -1L)
          || b.source <= lastTakerSource.getOrDefault(m.second(), -1L)) {
        metrics.decision("WAIT_NEW_DEPTH", null);
        continue;
      }
      List<String> resting = open(m);
      if (!resting.isEmpty()) {
        maintainResting(m, a, b, resting);
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
        cancelAll(m, "PRICE_BOUND_OR_STALE_TICK");
        metrics.decision("PRICE_BOUND_OR_STALE_TICK", null);
        continue;
      }
      BigDecimal edge = ONE.subtract(ap).subtract(bp),
          required =
              PairPolicy.requiredEdge(
                  cfg.minimumEdge(),
                  vols.getOrDefault(m.first(), ZERO).max(vols.getOrDefault(m.second(), ZERO)),
                  (m.endMs() - now) / 1000,
                  depth,
                  cfg.activationMs(),
                  ZERO);
      boolean small = q.compareTo(m.minSize()) < 0;
      boolean insufficientEdge =
          edge.multiply(q).subtract(cfg.mergeCost()).compareTo(required.multiply(q)) < 0;
      if (small || insufficientEdge) {
        cancelAll(m, small ? "ENTRY_MIN_SIZE" : "ENTRY_NET_EDGE");
        metrics.decision(
            small && insufficientEdge ? "MIN_SIZE_AND_NET_EDGE" : small ? "MIN_SIZE" : "NET_EDGE",
            edge);
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

  private JsonNode scopedGap(JsonNode data) {
    Set<String> tokens = DataGap.tokens(data);
    if (tokens.isEmpty()) return data;
    var affected = new TreeSet<String>(tokens);
    for (var market : markets.values())
      if (tokens.contains(market.first()) || tokens.contains(market.second())) {
        affected.add(market.first()); affected.add(market.second());
      }
    var scoped = (com.fasterxml.jackson.databind.node.ObjectNode) data.deepCopy();
    scoped.set("tokens", mapper.valueToTree(affected));
    return scoped;
  }

  private void maintainResting(ResearchMarket m, Book a, Book b, List<String> ids) {
    if (ids.stream().anyMatch(cancelRequested::contains)) {
      metrics.decision("WAIT_CANCEL_ACK", null);
      return;
    }
    var orders = ids.stream().map(id -> ledger.snapshot().orders().get(id)).toList();
    var first = orders.stream().filter(o -> o.token().equals(m.first())).findFirst().orElse(null);
    var second = orders.stream().filter(o -> o.token().equals(m.second())).findFirst().orElse(null);
    if (orders.size() != 2 || first == null || second == null || !first.buy() || !second.buy()
        || first.remaining().compareTo(second.remaining()) != 0) {
      cancelAll(m, "RESTING_INCOMPLETE_PAIR");
      metrics.decision("RESTING_INCOMPLETE_PAIR", null);
      return;
    }
    BigDecimal quantity = first.remaining(), edge = ONE.subtract(first.price()).subtract(second.price());
    boolean validPrices = first.price().remainder(m.tick()).signum() == 0
        && second.price().remainder(m.tick()).signum() == 0
        && first.price().compareTo(a.asks.firstKey()) < 0
        && second.price().compareTo(b.asks.firstKey()) < 0;
    BigDecimal depth = a.bids.lastEntry().getValue().min(b.bids.lastEntry().getValue());
    BigDecimal required = PairPolicy.requiredEdge(cfg.minimumEdge(),
        vols.getOrDefault(m.first(), ZERO).max(vols.getOrDefault(m.second(), ZERO)),
        (m.endMs()-now)/1000, depth, cfg.activationMs(), ZERO);
    if (!validPrices || edge.multiply(quantity).subtract(cfg.mergeCost()).compareTo(required.multiply(quantity)) < 0) {
      output.accept("RESTING_RISK_CHECK", Map.of(
          "at", now, "condition", m.condition(), "orderIds", ids,
          "quantity", quantity, "reservedGrossEdge", edge,
          "reservedNetEdge", edge.subtract(cfg.mergeCost().divide(quantity, 18, RoundingMode.UP)),
          "requiredEdge", required, "depth", depth,
          "volatility", vols.getOrDefault(m.first(), ZERO).max(vols.getOrDefault(m.second(), ZERO)),
          "validPrices", validPrices));
      cancelAll(m, validPrices ? "RESTING_NET_EDGE" : "RESTING_PRICE_INVALID");
      metrics.decision(validPrices ? "RESTING_NET_EDGE" : "RESTING_PRICE_INVALID", edge);
      return;
    }
    BigDecimal ap = bid(a, m.tick()), bp = bid(b, m.tick());
    BigDecimal replacementEdge = ONE.subtract(ap).subtract(bp);
    BigDecimal replacementSize = cfg.orderShares().min(depth.multiply(new BigDecimal("0.1"))).setScale(2, RoundingMode.DOWN);
    boolean competitiveImprovement = first.price().compareTo(a.bids.lastKey()) < 0
        || second.price().compareTo(b.bids.lastKey()) < 0;
    boolean replacementValid = ap.signum() > 0 && bp.signum() > 0
        && ap.compareTo(a.asks.firstKey()) < 0 && bp.compareTo(b.asks.firstKey()) < 0
        && replacementSize.compareTo(m.minSize()) >= 0
        && replacementEdge.multiply(replacementSize).subtract(cfg.mergeCost())
            .compareTo(required.multiply(replacementSize)) >= 0;
    if (competitiveImprovement && replacementValid && now - quoteAt.getOrDefault(m.condition(), now) >= 2000) {
      cancelAll(m, "REPRICE_VALIDATED_PAIR");
      metrics.decision("REPRICE_VALIDATED_PAIR", edge);
    } else metrics.decision("RESTING", edge);
  }

  private void reduce(ResearchMarket m, BigDecimal imbalance, Book a, Book b) {
    long age = now - unhedged.getOrDefault(m.condition(), now);
    boolean overdue = age >= cfg.unhedgedMs() || imbalance.abs().compareTo(cfg.maxUnhedged()) >= 0;
    long waitMs =
        PairPolicy.secondLegWaitMs(
            m.endMs() - now,
            cfg.unhedgedMs(),
            vols.getOrDefault(m.first(), ZERO).max(vols.getOrDefault(m.second(), ZERO)));
    if (age < waitMs && !overdue) {
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
      cancelAll(m, "CANCEL_BEFORE_RISK_EXIT");
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
            now
                + new LatencyProfile(cfg.activationMs(), cfg.latencyJitterMs(), cfg.latencySeed())
                    .delay("taker", m.condition() + ":" + token + ":" + now),
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
    if (externalMode) {
      Book book = books.get(token);
      BigDecimal volatility = vols.get(token);
      if (book != null && volatility != null && !book.bids.isEmpty() && !book.asks.isEmpty()) {
        BigDecimal inventory =
            holding(m.first())
                .shares()
                .subtract(holding(m.second()).shares())
                .divide(
                    holding(m.first()).shares().add(holding(m.second()).shares()).max(ONE),
                    18,
                    RoundingMode.HALF_EVEN);
        var features =
            Map.of(
                "spread",
                book.asks.firstKey().subtract(book.bids.lastKey()),
                "queue_ahead",
                (buy ? book.bids : book.asks)
                    .getOrDefault(price, ZERO)
                    .multiply(cfg.queueMultiplier()),
                "inventory_imbalance",
                inventory,
                "source_age_ms",
                now - book.source(),
                "seconds_to_expiry",
                BigDecimal.valueOf(m.endMs() - now).divide(BigDecimal.valueOf(1000)),
                "volatility",
                volatility);
        var featuresV2 = new TreeMap<String, Object>(features);
        BigDecimal bidDepth = book.bids.lastEntry().getValue(),
            askDepth = book.asks.firstEntry().getValue();
        BigDecimal localDepth = buy ? bidDepth : askDepth;
        featuresV2.put("order_size", q);
        featuresV2.put(
            "order_depth_ratio",
            q.divide(localDepth.max(new BigDecimal("0.000000001")), 18, RoundingMode.HALF_EVEN));
        featuresV2.put(
            "book_imbalance",
            bidDepth.subtract(askDepth).divide(bidDepth.add(askDepth), 18, RoundingMode.HALF_EVEN));
        output.accept(
            "ORDER_FEATURES",
            Map.of(
                "orderId",
                id,
                "marketId",
                m.condition(),
                "token",
                token,
                "submittedMs",
                now,
                "featureObservedMs",
                now,
                "provenance",
                "PAPER_MODEL",
                "features",
                features,
                "featuresV2",
                featuresV2,
                "quantity",
                q,
                "queueFeatureDefinition",
                "DISPLAYED_DEPTH_AT_SUBMISSION_TIMES_MODEL_MULTIPLIER"));
      } else
        output.accept(
            "FEATURES_UNAVAILABLE",
            Map.of("orderId", id, "at", now, "reason", "MISSING_CAUSAL_VOLATILITY_OR_DEPTH"));
    }
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

  public synchronized void restoreObservation(JsonNode data) {
    if (!externalMode
        || data.path("sequence").asLong() != inputSequence
        || data.path("generatedMs").asLong() < now)
      throw new IllegalArgumentException("Observation replay mismatch");
    observations.putIfAbsent(inputSequence, data.path("generatedMs").asLong());
    while (observations.size() > 1024) observations.remove(observations.keySet().iterator().next());
    output.accept("OBSERVATION", data);
  }

  public synchronized JsonNode externalReply(String id) {
    if (!externalReplies.containsKey(id)) throw new IllegalStateException("No PAPER response");
    return externalReplies.get(id).deepCopy();
  }

  private void processExternal(JsonNode proposal) {
    String clientId = proposal.path("id").asText();
    var response = mapper.createObjectNode();
    response
        .put("id", clientId)
        .put("virtualOnly", true)
        .put("executionEnabled", false)
        .put("liveAllowed", false);
    List<AccountLedger.OrderIntent> intents = new ArrayList<>();
    ResearchMarket[] membership;
    String prefix, fingerprint;
    try {
      if (!clientId.matches("[A-Za-z0-9_.:-]{1,128}"))
        throw new IllegalArgumentException("Invalid proposal id");
      prefix = "phase3:" + digest(clientId.getBytes(java.nio.charset.StandardCharsets.UTF_8)) + ":";
      // Canonical JSON field order makes network retries stable across object key ordering.
      var canonical = mapper.convertValue(proposal, java.util.TreeMap.class);
      fingerprint =
          digest(
              mapper
                  .writer()
                  .with(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
                  .writeValueAsBytes(canonical));
      List<String> existing =
          ledger.snapshot().orders().keySet().stream()
              .filter(id -> id.startsWith(prefix))
              .sorted()
              .toList();
      if (!existing.isEmpty()) {
        if (existing.size() != proposal.path("legs").size()
            || existing.stream().anyMatch(id -> !id.startsWith(prefix + fingerprint + ":")))
          throw new IllegalStateException("Idempotency key conflict");
        response.put("status", "PAPER_ALREADY_RECORDED");
        response.set("orders", mapper.valueToTree(existing));
        rememberExternal(clientId, response);
        return;
      }
      long observedSequence = proposal.path("sequence").asLong(-1);
      Long issued = observations.get(observedSequence);
      if (issued == null || now < issued || now - issued > 250)
        throw new IllegalStateException("Observation expired or never issued");
      if (!proposal.path("sessionId").asText().equals(sessionId))
        throw new IllegalStateException("Wrong session");
      var current = (com.fasterxml.jackson.databind.node.ObjectNode) proposal.deepCopy();
      current.put("sequence", inputSequence);
      var snapshot = exportSnapshot(now, false);
      externalValidator.validateForPaper(snapshot, current);
      membership = new ResearchMarket[proposal.path("legs").size()];
      int index = 0;
      for (var item : proposal.path("legs")) {
        String token = item.path("token").asText();
        intents.add(
            new AccountLedger.OrderIntent(
                prefix + fingerprint + ":" + index,
                token,
                item.path("buy").asBoolean(),
                PaperMatchingEngine.decimal(item, "price"),
                PaperMatchingEngine.decimal(item, "size")));
        membership[index++] = markets.get(item.path("condition").asText());
      }
      // Each leg may fill independently: a cheap quote must not bypass the share imbalance cap.
      for (var market : Arrays.stream(membership).distinct().toList()) {
        BigDecimal upper =
            holding(market.first()).shares().subtract(holding(market.second()).shares());
        BigDecimal lower = upper;
        for (var order : ledger.snapshot().orders().values()) {
          if (order.remaining().signum() <= 0) continue;
          if ((order.token().equals(market.first()) && order.buy())
              || (order.token().equals(market.second()) && !order.buy()))
            upper = upper.add(order.remaining());
          if ((order.token().equals(market.first()) && !order.buy())
              || (order.token().equals(market.second()) && order.buy()))
            lower = lower.subtract(order.remaining());
        }
        for (var intent : intents) {
          if ((intent.token().equals(market.first()) && intent.buy())
              || (intent.token().equals(market.second()) && !intent.buy()))
            upper = upper.add(intent.size());
          if ((intent.token().equals(market.first()) && !intent.buy())
              || (intent.token().equals(market.second()) && intent.buy()))
            lower = lower.subtract(intent.size());
        }
        if (upper.abs().max(lower.abs()).compareTo(cfg.maxUnhedged()) > 0)
          throw new IllegalStateException("Worst-case unhedged inventory limit");
      }
      // Validation failures never publish a partial reservation.
      ledger.reserveBatch(intents);
    } catch (Exception e) {
      if (ledger.persistenceFailed())
        throw new IllegalStateException("PAPER persistence failed", e);
      response.put("status", "PAPER_REJECTED").put("reason", String.valueOf(e.getMessage()));
      rememberExternal(clientId, response);
      return;
    }
    try {
      int i = 0;
      for (var intent : intents) {
        submit(
            intent.id(),
            membership[i++],
            intent.token(),
            intent.buy(),
            intent.price(),
            intent.size(),
            ZERO,
            "EXTERNAL_PAPER");
        externalCancelAt.put(intent.id(), now + 5000);
      }
      output.accept(
          "PROPOSAL_GROUP",
          Map.of(
              "groupId",
              prefix + fingerprint,
              "at",
              now,
              "orders",
              intents.stream()
                  .map(intent -> Map.of("id", intent.id(), "quantity", intent.size()))
                  .toList()));
      response.put("status", "PAPER_SUBMITTED");
      response.set(
          "orders",
          mapper.valueToTree(intents.stream().map(AccountLedger.OrderIntent::id).toList()));
      save();
      rememberExternal(clientId, response);
    } catch (RuntimeException e) {
      intents.forEach(intent -> ledger.cancel(intent.id()));
      suspend();
      throw e;
    }
  }

  private void processGroupSettlement(JsonNode event) {
    String id = event.path("id").asText();
    var receipt = mapper.createObjectNode();
    receipt
        .put("id", "settle:" + id)
        .put("virtualOnly", true)
        .put("executionEnabled", false)
        .put("liveAllowed", false);
    MultiOutcomeSettlement.Verified proof;
    try {
      proof = MultiOutcomeSettlement.verify(event, markets, resolutions, mapper);
      if (groupProofs.containsKey(id) && !groupProofs.get(id).equals(proof.membershipSha256()))
        throw new IllegalArgumentException("Terminal outcome membership changed");
    } catch (IllegalArgumentException e) {
      receipt.put("status", "PAPER_GROUP_DEFERRED").put("reason", e.getMessage());
      rememberExternal("settle:" + id, receipt);
      return;
    }
    groupProofs.put(id, proof.membershipSha256());
    save();
    BigDecimal quantity =
        proof.payouts().values().stream()
            .flatMap(m -> m.keySet().stream())
            .map(t -> holding(t).shares())
            .reduce(ZERO, BigDecimal::add);
    boolean changed =
        ledger.redeemBatch(
            "group-resolution:" + id,
            proof.payouts(),
            quantity.signum() > 0 ? cfg.redemptionCost() : ZERO);
    receipt
        .put("status", changed ? "PAPER_GROUP_REDEEMED" : "PAPER_GROUP_ALREADY_REDEEMED")
        .put("membershipSha256", proof.membershipSha256());
    outcomeGroups.remove(id);
    save();
    rememberExternal("settle:" + id, receipt);
  }

  private void rememberExternal(String id, JsonNode response) {
    externalReplies.put(id, response.deepCopy());
    while (externalReplies.size() > 1024)
      externalReplies.remove(externalReplies.keySet().iterator().next());
    output.accept("EXTERNAL_ACK", response);
  }

  private static String digest(byte[] data) {
    try {
      return java.util.HexFormat.of()
          .formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(data));
    } catch (java.security.NoSuchAlgorithmException e) {
      throw new IllegalStateException(e);
    }
  }

  public synchronized void cancel(String id) {
    cancel(id, "CLIENT_CANCEL");
  }

  private void cancel(String id, String reason) {
    var order = ledger.snapshot().orders().get(id);
    if (order == null || order.remaining().signum() <= 0 || !cancelRequested.add(id)) return;
    output.accept("CANCEL_REQUEST", Map.of("id", id, "reason", reason, "at", now));
    apply(matching.accept("CANCEL", now, node(Map.of("id", id, "reason", reason))));
  }

  private void cancelAll(ResearchMarket market, String reason) {
    for (String id : open(market)) cancel(id, reason);
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
        .add(tick.multiply(BigDecimal.valueOf(cfg.makerImprovementTicks())))
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
    return exportSnapshot(generatedAt, true);
  }

  private JsonNode exportSnapshot(long generatedAt, boolean issued) {
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
    result.put("paperExecutionEnabled", externalMode);
    if (externalMode && issued) {
      observations.putIfAbsent(inputSequence, generatedAt);
      while (observations.size() > 1024)
        observations.remove(observations.keySet().iterator().next());
      output.accept("OBSERVATION", Map.of("sequence", inputSequence, "generatedMs", generatedAt));
    }
    result.put("executionEnabled", false);
    result.put("liveAllowed", false);
    result.put("sessionId", sessionId);
    result.put("sequence", inputSequence);
    result.put("inputMs", now);
    result.put("generatedMs", generatedAt);
    result.put(
        "matchingAssumptions",
        Map.of(
            "queueMultiplier",
            cfg.queueMultiplier(),
            "activationMs",
            cfg.activationMs(),
            "cancelMs",
            cfg.cancelMs()));
    result.put("maxBookAgeMs", cfg.maxBookAgeMs());
    result.put("metadataMaxAgeMs", cfg.metadataMaxAgeMs());
    result.put("account", account);
    if (externalMode)
      result.put(
          "paperStatistics",
          Map.of(
              "matching",
              markouts.snapshot(generatedAt),
              "dataGaps",
              matching.gaps(),
              "riskBreaches",
              riskBreaches));
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
    r.put("makerExecutionDiagnostics", matching.diagnostics());
    r.putAll(markouts.snapshot(Math.max(now, 0)));
    var active = new ArrayList<Map<String, Object>>();
    for (var m : markets.values()) {
      if (now >= m.endMs() || resolutions.containsKey(m.condition())) continue;
      var row = new LinkedHashMap<String, Object>();
      Book a = books.get(m.first()), b = books.get(m.second());
      row.put("condition", m.condition());
      row.put("remainingMs", m.endMs() - now);
      row.put("accepting", m.accepting());
      row.put("freshBooks", fresh(a) && fresh(b));
      row.put(
          "oldestBookAgeMs",
          a == null || b == null ? null : now - Math.min(a.source(), b.source()));
      row.put(
          "inventoryImbalance", holding(m.first()).shares().subtract(holding(m.second()).shares()));
      active.add(row);
    }
    r.put("activeMarkets", active);
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
    if (externalValidator != null) externalValidator.close();
  }
}
