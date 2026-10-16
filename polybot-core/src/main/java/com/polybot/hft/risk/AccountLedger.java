package com.polybot.hft.risk;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.state.AtomicJsonState;
import java.math.*;
import java.nio.file.Path;
import java.time.*;
import java.util.*;

/** Durable paper-account accounting. All mutators commit before publishing new state. */
public final class AccountLedger implements AutoCloseable {
  public record Holding(BigDecimal shares, BigDecimal basis) {}

  public record Reservation(
      String token,
      boolean buy,
      BigDecimal price,
      BigDecimal remaining,
      BigDecimal original,
      BigDecimal filled,
      String status) {}

  public record State(
      int version,
      BigDecimal cash,
      BigDecimal realized,
      BigDecimal fees,
      BigDecimal peakEquity,
      BigDecimal dayStartEquity,
      LocalDate day,
      boolean halted,
      Map<String, Holding> holdings,
      Map<String, Reservation> orders,
      Set<String> executions) {}

  public record Limits(
      BigDecimal maxOrder,
      BigDecimal maxTokenExposure,
      BigDecimal maxGrossExposure,
      BigDecimal dailyLoss,
      BigDecimal drawdown) {
    public Limits {
      for (BigDecimal value :
          List.of(maxOrder, maxTokenExposure, maxGrossExposure, dailyLoss, drawdown))
        if (value.signum() <= 0) throw new IllegalArgumentException("Risk limits must be positive");
    }
  }

  private final AtomicJsonState file;
  private final ObjectMapper mapper;
  private final Limits limits;
  private final Clock clock;
  private State state;
  private boolean failed;

  public AccountLedger(
      Path path, ObjectMapper mapper, BigDecimal capital, Limits limits, Clock clock) {
    this.mapper = mapper;
    this.limits = limits;
    this.clock = clock;
    file = new AtomicJsonState(path, mapper);
    var node = file.load();
    if (node == null) {
      if (capital.signum() <= 0)
        throw new IllegalArgumentException("Positive starting capital required");
      state =
          new State(
              1,
              capital,
              BigDecimal.ZERO,
              BigDecimal.ZERO,
              capital,
              capital,
              LocalDate.now(clock),
              false,
              Map.of(),
              Map.of(),
              Set.of());
      file.save(state);
    } else {
      state = mapper.convertValue(node, State.class);
      if (state.version() != 1
          || state.cash() == null
          || state.cash().signum() < 0
          || state.orders() == null
          || state.holdings() == null
          || state.executions() == null) throw new IllegalStateException("Invalid ledger snapshot");
      for (var h : state.holdings().values())
        if (h.shares().signum() < 0 || h.basis().signum() < 0)
          throw new IllegalStateException("Negative restored holding");
      for (var o : state.orders().values())
        if (o.remaining().signum() < 0
            || o.filled() == null
            || o.filled().signum() < 0
            || o.remaining().add(o.filled()).compareTo(o.original()) > 0)
          throw new IllegalStateException("Invalid restored order");
      if (available(state).signum() < 0)
        throw new IllegalStateException("Restored reservations exceed cash");
    }
  }

  public synchronized State snapshot() {
    return state;
  }

  public synchronized BigDecimal availableCash() {
    return available(state);
  }

  private static BigDecimal available(State s) {
    BigDecimal reserved =
        s.orders().values().stream()
            .filter(Reservation::buy)
            .map(o -> o.price().multiply(o.remaining()))
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    return s.cash().subtract(reserved);
  }

  private void commit(State next) {
    if (failed) throw new IllegalStateException("Persistence failed; account requires recovery");
    if (next.equals(state)) return;
    try {
      file.save(next);
      state = next;
    } catch (RuntimeException e) {
      failed = true;
      throw e;
    }
  }

  private void healthy() {
    if (failed || state.halted())
      throw new IllegalStateException("Account halted; reconciliation required");
  }

  private State next(
      BigDecimal cash,
      BigDecimal realized,
      BigDecimal fees,
      Map<String, Holding> holdings,
      Map<String, Reservation> orders,
      Set<String> executions) {
    return new State(
        1,
        cash,
        realized,
        fees,
        state.peakEquity(),
        state.dayStartEquity(),
        state.day(),
        state.halted(),
        Map.copyOf(holdings),
        Map.copyOf(orders),
        Set.copyOf(executions));
  }

  public synchronized void reserve(
      String id, String token, boolean buy, BigDecimal price, BigDecimal size) {
    healthy();
    commit(reserved(state, id, token, buy, price, size));
  }

  /** Both legs commit together; validation failure leaves no one-sided reservation. */
  public synchronized void reservePair(
      String upId,
      String up,
      String downId,
      String down,
      BigDecimal upPrice,
      BigDecimal downPrice,
      BigDecimal size) {
    healthy();
    if (up.equals(down) || upId.equals(downId))
      throw new IllegalArgumentException("Distinct pair required");
    State first = reserved(state, upId, up, true, upPrice, size);
    commit(reserved(first, downId, down, true, downPrice, size));
  }

  private State reserved(
      State view, String id, String token, boolean buy, BigDecimal price, BigDecimal size) {
    if (view.orders().containsKey(id)) throw new IllegalArgumentException("Duplicate order");
    if (price.signum() <= 0 || price.compareTo(BigDecimal.ONE) >= 0 || size.signum() <= 0)
      throw new IllegalArgumentException("Invalid price or size");
    BigDecimal cost = price.multiply(size);
    if (cost.compareTo(limits.maxOrder()) > 0)
      throw new IllegalStateException("Order cap exceeded");
    if (buy) {
      if (cost.compareTo(available(view)) > 0)
        throw new IllegalStateException("Insufficient available cash");
      BigDecimal tokenExposure =
          view.holdings()
              .getOrDefault(token, new Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .basis();
      BigDecimal gross =
          view.holdings().values().stream()
              .map(Holding::basis)
              .reduce(BigDecimal.ZERO, BigDecimal::add);
      for (var o : view.orders().values())
        if (o.buy()) {
          BigDecimal value = o.price().multiply(o.remaining());
          gross = gross.add(value);
          if (o.token().equals(token)) tokenExposure = tokenExposure.add(value);
        }
      if (tokenExposure.add(cost).compareTo(limits.maxTokenExposure()) > 0
          || gross.add(cost).compareTo(limits.maxGrossExposure()) > 0)
        throw new IllegalStateException("Inventory exposure cap exceeded");
    } else {
      BigDecimal reserved =
          view.orders().values().stream()
              .filter(o -> !o.buy() && o.token().equals(token))
              .map(Reservation::remaining)
              .reduce(BigDecimal.ZERO, BigDecimal::add);
      if (view.holdings()
              .getOrDefault(token, new Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .shares()
              .subtract(reserved)
              .compareTo(size)
          < 0) throw new IllegalStateException("Insufficient available inventory");
    }
    var orders = new HashMap<>(view.orders());
    orders.put(id, new Reservation(token, buy, price, size, size, BigDecimal.ZERO, "OPEN"));
    return next(
        view.cash(), view.realized(), view.fees(), view.holdings(), orders, view.executions());
  }

  public synchronized boolean fill(
      String executionId, String orderId, BigDecimal quantity, BigDecimal price, BigDecimal fee) {
    if (state.executions().contains(executionId)) return false;
    if (failed) throw new IllegalStateException("Persistence failed");
    Reservation o = state.orders().get(orderId);
    if (o == null) throw new IllegalStateException("Unknown order");
    if (quantity.signum() <= 0
        || quantity.compareTo(o.remaining()) > 0
        || fee.signum() < 0
        || price.signum() <= 0) throw new IllegalArgumentException("Invalid fill");
    if (o.buy() ? price.compareTo(o.price()) > 0 : price.compareTo(o.price()) < 0)
      throw new IllegalArgumentException("Fill violates limit");
    var holdings = new HashMap<>(state.holdings());
    Holding h = holdings.getOrDefault(o.token(), new Holding(BigDecimal.ZERO, BigDecimal.ZERO));
    BigDecimal value = price.multiply(quantity), cash = state.cash(), realized = state.realized();
    if (o.buy()) {
      cash = cash.subtract(value).subtract(fee);
      if (cash.signum() < 0) throw new IllegalStateException("Fill exceeds cash");
      h = new Holding(h.shares().add(quantity), h.basis().add(value).add(fee));
    } else {
      if (quantity.compareTo(h.shares()) > 0)
        throw new IllegalStateException("Fill exceeds inventory");
      BigDecimal basis =
          h.basis().multiply(quantity).divide(h.shares(), 18, RoundingMode.HALF_EVEN);
      cash = cash.add(value).subtract(fee);
      realized = realized.add(value).subtract(fee).subtract(basis);
      h = new Holding(h.shares().subtract(quantity), h.basis().subtract(basis));
    }
    holdings.put(o.token(), h);
    var orders = new HashMap<>(state.orders());
    BigDecimal remaining = o.remaining().subtract(quantity);
    orders.put(
        orderId,
        new Reservation(
            o.token(),
            o.buy(),
            o.price(),
            remaining,
            o.original(),
            o.filled().add(quantity),
            remaining.signum() == 0 ? "FILLED" : "PARTIALLY_FILLED"));
    var ids = new HashSet<>(state.executions());
    ids.add(executionId);
    State next = next(cash, realized, state.fees().add(fee), holdings, orders, ids);
    if (available(next).signum() < 0)
      throw new IllegalStateException("Fill consumes reserved cash");
    commit(next);
    return true;
  }

  public synchronized void cancel(String id) {
    var orders = new HashMap<>(state.orders());
    Reservation o = orders.get(id);
    if (o != null && o.remaining().signum() > 0) {
      orders.put(
          id,
          new Reservation(
              o.token(),
              o.buy(),
              o.price(),
              BigDecimal.ZERO,
              o.original(),
              o.filled(),
              "CANCELED"));
      commit(
          next(
              state.cash(),
              state.realized(),
              state.fees(),
              state.holdings(),
              orders,
              state.executions()));
    }
  }

  /**
   * Virtual complete-set redemption. Caller must verify token membership in the SAME binary
   * condition.
   */
  public synchronized boolean merge(
      String operation, String up, String down, BigDecimal quantity, BigDecimal cost) {
    if (up.equals(down) || quantity.signum() <= 0 || cost.signum() < 0)
      throw new IllegalArgumentException("Invalid merge");
    return settle(operation, Map.of(up, quantity, down, quantity), quantity, cost);
  }

  /** Explicit verified resolution payouts; never infer resolution from an expiring quote. */
  public synchronized boolean redeem(
      String operation, Map<String, BigDecimal> payouts, BigDecimal cost) {
    if (payouts.isEmpty() || cost.signum() < 0)
      throw new IllegalArgumentException("Invalid redemption");
    var quantities = new HashMap<String, BigDecimal>();
    BigDecimal proceeds = BigDecimal.ZERO;
    for (var e : payouts.entrySet()) {
      if (e.getValue().signum() < 0 || e.getValue().compareTo(BigDecimal.ONE) > 0)
        throw new IllegalArgumentException("Invalid payout");
      BigDecimal q =
          state
              .holdings()
              .getOrDefault(e.getKey(), new Holding(BigDecimal.ZERO, BigDecimal.ZERO))
              .shares();
      quantities.put(e.getKey(), q);
      proceeds = proceeds.add(q.multiply(e.getValue()));
    }
    return settle(operation, quantities, proceeds, cost);
  }

  private boolean settle(
      String operation, Map<String, BigDecimal> quantities, BigDecimal proceeds, BigDecimal cost) {
    if (state.executions().contains(operation)) return false;
    if (failed) throw new IllegalStateException("Persistence failed");
    var holdings = new HashMap<>(state.holdings());
    BigDecimal removed = BigDecimal.ZERO;
    for (var e : quantities.entrySet()) {
      var h = holdings.getOrDefault(e.getKey(), new Holding(BigDecimal.ZERO, BigDecimal.ZERO));
      BigDecimal reserved =
          state.orders().values().stream()
              .filter(o -> !o.buy() && o.token().equals(e.getKey()))
              .map(Reservation::remaining)
              .reduce(BigDecimal.ZERO, BigDecimal::add);
      if (e.getValue().compareTo(h.shares().subtract(reserved)) > 0)
        throw new IllegalStateException("Settlement uses reserved inventory");
      BigDecimal basis =
          h.shares().signum() == 0
              ? BigDecimal.ZERO
              : h.basis().multiply(e.getValue()).divide(h.shares(), 18, RoundingMode.HALF_EVEN);
      removed = removed.add(basis);
      holdings.put(
          e.getKey(), new Holding(h.shares().subtract(e.getValue()), h.basis().subtract(basis)));
    }
    BigDecimal cash = state.cash().add(proceeds).subtract(cost);
    var ids = new HashSet<>(state.executions());
    ids.add(operation);
    State result =
        next(
            cash,
            state.realized().add(proceeds).subtract(removed).subtract(cost),
            state.fees().add(cost),
            holdings,
            state.orders(),
            ids);
    if (available(result).signum() < 0) throw new IllegalStateException("Settlement exceeds cash");
    commit(result);
    return true;
  }

  public synchronized BigDecimal mark(Map<String, BigDecimal> bids) {
    BigDecimal equity = state.cash();
    for (var e : state.holdings().entrySet())
      if (e.getValue().shares().signum() > 0) {
        BigDecimal bid = bids.get(e.getKey());
        if (bid == null || bid.signum() < 0 || bid.compareTo(BigDecimal.ONE) > 0)
          throw new IllegalStateException("Missing valid inventory mark");
        equity = equity.add(e.getValue().shares().multiply(bid));
      }
    LocalDate day = LocalDate.now(clock);
    BigDecimal start = day.equals(state.day()) ? state.dayStartEquity() : equity;
    BigDecimal peak = state.peakEquity().max(equity);
    boolean halted =
        state.halted()
            || start.subtract(equity).compareTo(limits.dailyLoss()) >= 0
            || peak.subtract(equity).compareTo(limits.drawdown()) >= 0;
    commit(
        new State(
            1,
            state.cash(),
            state.realized(),
            state.fees(),
            peak,
            start,
            day,
            halted,
            state.holdings(),
            state.orders(),
            state.executions()));
    return equity;
  }

  public synchronized void halt() {
    commit(
        new State(
            1,
            state.cash(),
            state.realized(),
            state.fees(),
            state.peakEquity(),
            state.dayStartEquity(),
            state.day(),
            true,
            state.holdings(),
            state.orders(),
            state.executions()));
  }

  public void close() {
    file.close();
  }
}
