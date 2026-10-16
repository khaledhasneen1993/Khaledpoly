package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.io.*;
import java.math.*;
import java.nio.file.*;
import java.time.*;
import java.util.*;

/** Replays a single executor tape in receive order. Never sorts by exchange timestamp. */
public final class ReplayRunner {
  public static Map<String, Object> run(
      Path tape, Path workspace, boolean stress, ObjectMapper mapper) throws IOException {
    Files.createDirectories(workspace);
    var metrics = new PaperMetrics();
    var outputFills = new ArrayList<PaperMatchingEngine.Fill>();
    var pairs = new TreeMap<String, JsonNode>();
    var marks = new HashMap<String, BigDecimal>();
    PaperMatchingEngine matching = null;
    AccountLedger ledger = null;
    long seq = 0, at = 0, start = -1;
    String run = null, lastKind = "";
    int breaches = 0;
    BigDecimal initial = null,
        initialRealized = null,
        peak = null,
        maxDrawdown = BigDecimal.ZERO,
        mergeCost = null;
    boolean stopped = false, fillsEnabled = false;
    var warnings = new ArrayList<String>();
    var clock = new ReplayClock();
    try (var lines = Files.newBufferedReader(tape)) {
      String line;
      while ((line = lines.readLine()) != null) {
        if (line.isBlank()) throw new IllegalArgumentException("Blank tape row");
        JsonNode row = mapper.readTree(line), data = row.path("data");
        if (row.path("schema").asInt() != 1 || row.path("seq").asLong() != ++seq)
          throw new IllegalArgumentException("Tape sequence gap");
        if (run == null) run = PaperMatchingEngine.required(row, "runId");
        if (!run.equals(row.path("runId").asText()))
          throw new IllegalArgumentException("Mixed runs");
        long nextAt = row.path("arrivalMs").asLong(-1);
        if (nextAt < at) throw new IllegalArgumentException("Receive clock regression");
        at = nextAt;
        clock.at = at;
        if (start < 0) start = at;
        String kind = PaperMatchingEngine.required(row, "kind");
        lastKind = kind;
        if (kind.equals("MATCHING_CONFIG")) {
          if (matching != null) throw new IllegalArgumentException("Duplicate matching config");
          matching =
              new PaperMatchingEngine(
                  stress ? 1000 : data.path("activationMs").asLong(),
                  stress ? 1000 : data.path("cancelMs").asLong(),
                  data.path("maxBookAgeMs").asLong(),
                  stress
                      ? new BigDecimal("4")
                      : PaperMatchingEngine.decimal(data, "queueMultiplier"));
          fillsEnabled = data.path("fillsEnabled").asBoolean();
          mergeCost = PaperMatchingEngine.decimal(data, "mergeCost");
          if (stress) mergeCost = mergeCost.add(new BigDecimal("0.05"));
          Path state = workspace.resolve("ledger.json");
          if (Files.exists(state))
            throw new IllegalArgumentException("Replay workspace must be empty");
          Files.writeString(
              state,
              mapper.writeValueAsString(data.path("account")),
              StandardOpenOption.CREATE_NEW);
          // Restore exactly the initial account and risk limits, including existing cash, fills,
          // and halt.
          JsonNode limits = data.path("limits");
          ledger =
              new AccountLedger(
                  state,
                  mapper,
                  new BigDecimal("500"),
                  mapper.treeToValue(limits, AccountLedger.Limits.class),
                  clock);
          for (var id : List.copyOf(ledger.snapshot().orders().keySet())) ledger.cancel(id);
          data.path("pairs").fields().forEachRemaining(e -> pairs.put(e.getKey(), e.getValue()));
          initial = ledger.snapshot().cash();
          initialRealized = ledger.snapshot().realized();
          peak = initial;
          if (!ledger.snapshot().holdings().values().stream()
              .allMatch(h -> h.shares().signum() == 0))
            warnings.add("Initial inventory exists: starting equity requires external marks");
          continue;
        }
        if (matching == null) continue; // raw startup events before account initialization
        if (kind.equals("ACCOUNT_MARK")) {
          var recordedMarks = new HashMap<String, BigDecimal>();
          data.fields()
              .forEachRemaining(
                  e -> recordedMarks.put(e.getKey(), new BigDecimal(e.getValue().asText())));
          try {
            ledger.mark(recordedMarks);
          } catch (IllegalStateException e) {
            warnings.add("Mark unavailable: " + e.getMessage());
          }
          if (ledger.snapshot().halted()) {
            stopped = true;
            breaches++;
          }
        }
        if (kind.equals("PAIR_MARKET")) pairs.put(data.path("condition").asText(), data);
        if (kind.equals("PAIR_RESERVATION") && !stopped) {
          var u = data.path("up");
          var d = data.path("down");
          try {
            ledger.reservePair(
                u.path("clientOrderId").asText(),
                u.path("tokenId").asText(),
                d.path("clientOrderId").asText(),
                d.path("tokenId").asText(),
                PaperMatchingEngine.decimal(u, "price"),
                PaperMatchingEngine.decimal(d, "price"),
                PaperMatchingEngine.decimal(u, "size"));
          } catch (RuntimeException e) {
            breaches++;
            stopped = true;
            warnings.add("Reservation rejected: " + e.getMessage());
          }
        }
        if (!kind.startsWith("MATCH_")) continue;
        String input = kind.substring(6);
        if (input.equals("TRADE") && !fillsEnabled) continue;
        if (input.equals("ORDER")) {
          if (stopped) continue;
          String id = data.path("id").asText();
          try {
            if (!ledger.snapshot().orders().containsKey(id))
              ledger.reserve(
                  id,
                  data.path("token").asText(),
                  data.path("side").asText().equals("BUY"),
                  PaperMatchingEngine.decimal(data, "price"),
                  PaperMatchingEngine.decimal(data, "size"));
          } catch (RuntimeException e) {
            breaches++;
            stopped = true;
            warnings.add("Order rejected: " + e.getMessage());
            continue;
          }
        }
        var update = matching.accept(input, at, data);
        if (input.equals("BOOK")) {
          metrics.book(data, at);
          BigDecimal bid = BigDecimal.ZERO;
          for (var level : data.path("bids"))
            bid = bid.max(PaperMatchingEngine.decimal(level, "price"));
          marks.put(data.path("token").asText(), bid);
        }
        for (var f : update.fills()) {
          ledger.fill("replay:" + seq + ":" + f.id(), f.id(), f.size(), f.price(), BigDecimal.ZERO);
          metrics.fill(f);
          outputFills.add(f);
        }
        for (var e : update.terminal().entrySet())
          if (!e.getValue().equals("FILLED")) ledger.cancel(e.getKey());
        if (!update.fills().isEmpty())
          for (var p : pairs.values()) {
            String up = p.path("up").asText(), down = p.path("down").asText();
            var h = ledger.snapshot().holdings();
            BigDecimal q =
                h.getOrDefault(up, new AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
                    .shares()
                    .min(
                        h.getOrDefault(
                                down, new AccountLedger.Holding(BigDecimal.ZERO, BigDecimal.ZERO))
                            .shares());
            if (q.compareTo(mergeCost) > 0)
              ledger.merge("merge:" + seq + ":" + up, up, down, q, mergeCost);
          }
        BigDecimal equity = ledger.snapshot().cash();
        for (var e : ledger.snapshot().holdings().entrySet())
          equity =
              equity.add(
                  e.getValue().shares().multiply(marks.getOrDefault(e.getKey(), BigDecimal.ZERO)));
        peak = peak.max(equity);
        maxDrawdown = maxDrawdown.max(peak.subtract(equity));
      }
      if (ledger == null) throw new IllegalArgumentException("Executor matching config missing");
      var report = new LinkedHashMap<String, Object>();
      report.put("schema", 1);
      report.put("stress", stress);
      report.put("runId", run);
      report.put("rows", seq);
      report.put("durationMs", at - start);
      report.put("initialCash", initial);
      report.put("cash", ledger.snapshot().cash());
      report.put("availableCash", ledger.availableCash());
      report.put("netRealizedPnl", ledger.snapshot().realized().subtract(initialRealized));
      report.put("feesAndSettlementCosts", ledger.snapshot().fees());
      report.put("maxDrawdown", maxDrawdown);
      report.put("holdings", ledger.snapshot().holdings());
      report.put("fills", outputFills);
      report.put("metrics", metrics.snapshot(at));
      report.put("dataGaps", matching.gaps());
      report.put("duplicates", matching.duplicates());
      report.put("riskBreaches", breaches);
      report.put("recordingClosedCleanly", lastKind.equals("RUN_END"));
      report.put("fillsEnabled", fillsEnabled);
      warnings.add(
          "Action replay freezes recorded decisions; stress is NOT a strategy rerun or a heldout"
              + " performance result");
      warnings.add(
          "Verified market resolutions and chronological heldout provenance are not supplied by"
              + " this tape");
      report.put("warnings", warnings);
      report.put("decision", "NO_GO");
      report.put(
          "reason",
          "Insufficient independently verified heldout markets/resolutions; no profitability"
              + " claim");
      return report;
    } finally {
      if (ledger != null) ledger.close();
    }
  }

  private static class ReplayClock extends Clock {
    long at;

    public ZoneId getZone() {
      return ZoneOffset.UTC;
    }

    public Clock withZone(ZoneId zone) {
      return this;
    }

    public Instant instant() {
      return Instant.ofEpochMilli(at);
    }
  }
}
