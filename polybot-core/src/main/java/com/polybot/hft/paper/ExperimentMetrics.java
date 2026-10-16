package com.polybot.hft.paper;

import java.math.*;
import java.util.*;

/** Join decisions and executions by order id; unavailable metrics stay explicitly absent. */
public final class ExperimentMetrics {
  private record Intent(long at, String condition, BigDecimal edge, String purpose) {}

  private final Map<String, Intent> intents = new HashMap<>();
  private final Map<String, Long> firstFill = new HashMap<>();
  private final Map<String, Long> reasons = new TreeMap<>();
  private final List<Map<String, Object>> executions = new ArrayList<>(),
      completions = new ArrayList<>();
  private final Map<String, Integer> edgeBuckets = new TreeMap<>();
  private BigDecimal bought = BigDecimal.ZERO,
      paired = BigDecimal.ZERO,
      peak = BigDecimal.ZERO,
      drawdown = BigDecimal.ZERO;
  private long decisions, missingMarks, expired;
  private BigDecimal expiryResidual = BigDecimal.ZERO;

  public void intent(String id, long at, String market, BigDecimal edge, String purpose) {
    intents.put(id, new Intent(at, market, edge, purpose));
  }

  public void decision(String reason, BigDecimal edge) {
    decisions++;
    reasons.merge(reason, 1L, Long::sum);
    if (edge != null)
      edgeBuckets.merge(edge.setScale(2, RoundingMode.FLOOR).toPlainString(), 1, Integer::sum);
  }

  public void fill(PaperMatchingEngine.Fill f, BigDecimal fee, String liquidity) {
    Intent i = intents.get(f.id());
    if (f.buy()) bought = bought.add(f.size());
    if (i != null) firstFill.putIfAbsent(i.condition, f.at());
    var e = new LinkedHashMap<String, Object>();
    e.put("orderId", f.id());
    e.put("at", f.at());
    e.put("token", f.token());
    e.put("buy", f.buy());
    e.put("size", f.size());
    e.put("price", f.price());
    e.put("fee", fee);
    e.put("liquidity", liquidity);
    e.put("condition", i == null ? null : i.condition);
    e.put("purpose", i == null ? null : i.purpose);
    e.put("expectedEdge", i == null ? null : i.edge);
    e.put("decisionToFillMs", i == null ? null : f.at() - i.at);
    executions.add(e);
  }

  public void merge(String condition, long at, BigDecimal quantity, BigDecimal realized) {
    paired = paired.add(quantity.multiply(BigDecimal.valueOf(2)));
    Long first = firstFill.remove(condition);
    var row = new LinkedHashMap<String, Object>();
    row.put("condition", condition);
    row.put("at", at);
    row.put("quantity", quantity);
    row.put("netRealizedEdgePerSet", realized.divide(quantity, 12, RoundingMode.HALF_EVEN));
    row.put("completionMs", first == null ? null : at - first);
    completions.add(row);
  }

  public void equity(BigDecimal value, boolean fresh) {
    if (!fresh) missingMarks++;
    peak = peak.max(value);
    drawdown = drawdown.max(peak.subtract(value));
  }

  public long resolvedTraded(Set<String> resolved) {
    return executions.stream()
        .map(e -> e.get("condition"))
        .filter(Objects::nonNull)
        .distinct()
        .filter(resolved::contains)
        .count();
  }

  public void expiry(BigDecimal residual) {
    expired++;
    expiryResidual = expiryResidual.add(residual);
  }

  public Map<String, Object> report() {
    var r = new LinkedHashMap<String, Object>();
    r.put("decisions", decisions);
    r.put("decisionReasons", Map.copyOf(reasons));
    r.put("edgeDistribution", Map.copyOf(edgeBuckets));
    r.put("executions", List.copyOf(executions));
    r.put("pairCompletions", List.copyOf(completions));
    r.put(
        "quantityPairCompletion",
        bought.signum() == 0 ? null : paired.divide(bought, 8, RoundingMode.DOWN));
    r.put("maxDrawdown", drawdown);
    r.put("missingMarkObservations", missingMarks);
    r.put("expiredMarkets", expired);
    r.put("residualExpiryWorstCaseNotional", expiryResidual);
    return r;
  }
}
