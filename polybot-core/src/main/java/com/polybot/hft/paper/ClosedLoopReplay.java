package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.nio.file.*;
import java.time.*;
import java.util.*;

/**
 * Runs the actual ResearchSession strategy on independent public observations; ignores ALL recorded
 * actions.
 */
public final class ClosedLoopReplay {
  public static Map<String, Object> run(
      Path tape,
      Path out,
      ResearchConfig config,
      AccountLedger.Limits limits,
      ObjectMapper mapper,
      boolean raw)
      throws Exception {
    return run(tape, out, config, limits, mapper, raw, Long.MIN_VALUE, Long.MAX_VALUE, "");
  }

  public static Map<String, Object> run(
      Path tape,
      Path out,
      ResearchConfig config,
      AccountLedger.Limits limits,
      ObjectMapper mapper,
      boolean raw,
      long windowStart,
      long windowEnd,
      String freezeSha)
      throws Exception {
    if (windowStart >= windowEnd) throw new IllegalArgumentException("Empty heldout window");
    if (Files.exists(out)) throw new IllegalArgumentException("Replay output must not exist");
    Files.createDirectories(out);
    var clock = new VirtualClock();
    var audit = new ArrayList<Map<String, Object>>();
    var normalizer = new RawTapeNormalizer(mapper);
    boolean clean = false, declared = false;
    long seq = 0,
        first = -1,
        last = -1,
        rawTick = -1,
        maxInputGap = 0,
        previousInput = -1,
        maxLag = 0;
    String runId = null, revision = "unrecorded";
    var manifest = tape.resolveSibling("manifest.json");
    if (Files.exists(manifest))
      revision = mapper.readTree(Files.readString(manifest)).path("revision").asText("unrecorded");
    var marketDays = new TreeSet<String>();
    var initialMetadata = new TreeMap<String, JsonNode>();
    boolean started = false;
    try (var ledger =
            new AccountLedger(
                out.resolve("ledger.json"), mapper, config.initialCash(), limits, clock);
        var session =
            new ResearchSession(
                ledger,
                config,
                mapper,
                out.resolve("session.json"),
                (kind, data) ->
                    audit.add(Map.of("kind", kind, "at", clock.millis(), "data", data)));
        var reader = Files.newBufferedReader(tape)) {
      String line;
      while ((line = reader.readLine()) != null) {
        JsonNode row = mapper.readTree(line);
        if (row == null || row.path("schema").asInt() != 1 || row.path("seq").asLong() != ++seq)
          throw new IllegalArgumentException("Invalid sequence/schema");
        String run = PaperMatchingEngine.required(row, "runId");
        if (runId == null) runId = run;
        else if (!runId.equals(run)) throw new IllegalArgumentException("Mixed dataset runs");
        long at = row.path("arrivalMs").asLong(-1);
        if (at < 0 || at < last) throw new IllegalArgumentException("Receive clock regression");
        if (first < 0) first = at;
        last = at;
        String kind = row.path("kind").asText();
        JsonNode data = row.path("data");
        clean = kind.equals("RUN_END");
        if (kind.equals("DATASET_CONFIG")) {
          declared =
              data.path("strategyIndependent").asBoolean(false)
                  && data.path("format").asText().equals("normalized-public-v1");
          continue;
        }
        if (at < windowStart) {
          if (kind.equals("RESEARCH_META"))
            initialMetadata.put(data.path("condition").asText(), data);
          continue;
        }
        if (at > windowEnd) continue;
        if (!started) {
          started = true;
          clock.at = at;
          for (var meta : initialMetadata.values())
            if (meta.path("endMs").asLong() > windowStart) session.accept("META", at, meta);
        }
        if (raw) {
          if (rawTick < 0) rawTick = at;
          while (rawTick < at) {
            clock.at = rawTick;
            session.accept("TICK", rawTick, mapper.createObjectNode());
            rawTick += config.decisionMillis();
          }
        }
        clock.at = at;
        if (raw && kind.equals("RAW_MARKET")) {
          normalizer.accept(
              data.path("text").asText(), at, (type, n) -> session.accept(type, at, n));
        } else if (kind.startsWith("RESEARCH_")) {
          if (previousInput >= 0) maxInputGap = Math.max(maxInputGap, at - previousInput);
          previousInput = at;
          if (data.has("sourceMs")) maxLag = Math.max(maxLag, at - data.path("sourceMs").asLong());
          String input = kind.substring(9);
          if (input.equals("FEED_ERROR")) input = "GAP";
          if (raw && Set.of("BOOK", "TRADE", "TICK").contains(input)) continue;
          if (input.equals("META")) {
            var m = mapper.convertValue(data, ResearchMarket.class);
            marketDays.add(
                Instant.ofEpochMilli(m.startMs()).atZone(ZoneOffset.UTC).toLocalDate().toString());
          }
          session.accept(input, at, data);
        }
      }
      var result = new LinkedHashMap<String, Object>(session.report());
      result.put("schema", 2);
      result.put("windowStartMs", windowStart);
      result.put("windowEndMs", windowEnd);
      result.put("freezeSha256", freezeSha);
      result.put("replayMode", "closed-loop");
      result.put("maxInputGapMs", maxInputGap);
      result.put("maxSourceLagMs", maxLag);
      result.put("inputFormat", raw ? "raw-market" : "normalized-public-v1");
      result.put("strategyIndependentDataset", declared);
      result.put("recordingClosedCleanly", clean);
      result.put("revision", revision);
      result.put(
          "strategyRevision",
          System.getProperty(
              "paper.replay.revision", System.getenv().getOrDefault("GITHUB_SHA", "unrecorded")));
      result.put("firstArrivalMs", first);
      result.put("lastArrivalMs", last);
      result.put("marketDays", marketDays);
      result.put("inputSha256", sha256(tape));
      result.put("configSha256", sha256(mapper.writeValueAsBytes(config)));
      result.put("rows", seq);
      result.put("decision", "NO_GO");
      result.put(
          "reason",
          "Evaluate frozen heldout baseline and stress reports against acceptance criteria");
      Files.writeString(
          out.resolve("audit.jsonl"),
          String.join(
                  "\n",
                  audit.stream()
                      .map(
                          a -> {
                            try {
                              return mapper.writeValueAsString(a);
                            } catch (Exception e) {
                              throw new IllegalStateException(e);
                            }
                          })
                      .toList())
              + "\n");
      Files.writeString(
          out.resolve("report.json"),
          mapper.writerWithDefaultPrettyPrinter().writeValueAsString(result));
      return result;
    }
  }

  public static String sha256(Path path) throws Exception {
    try (var in = Files.newInputStream(path)) {
      var md = java.security.MessageDigest.getInstance("SHA-256");
      byte[] b = new byte[65536];
      int n;
      while ((n = in.read(b)) != -1) md.update(b, 0, n);
      return java.util.HexFormat.of().formatHex(md.digest());
    }
  }

  public static String sha256(byte[] bytes) throws Exception {
    return java.util.HexFormat.of()
        .formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
  }

  public static final class VirtualClock extends Clock {
    public long at;

    public ZoneId getZone() {
      return ZoneOffset.UTC;
    }

    public Clock withZone(ZoneId z) {
      return this;
    }

    public Instant instant() {
      return Instant.ofEpochMilli(at);
    }
  }
}
