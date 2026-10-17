package com.polybot.hft.executor.replay;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.paper.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;

public final class ClosedLoopMain {
  public static void main(String[] args) throws Exception {
    if (args.length < 3)
      throw new IllegalArgumentException(
          "Usage: closed-loop DATA.jsonl NEW-OUT CONFIG.json [--stress] [--raw]");
    String freezePath = null;
    for (int i = 3; i < args.length; i++)
      if (args[i].equals("--freeze")) {
        if (i + 1 >= args.length) throw new IllegalArgumentException("Missing freeze file");
        freezePath = args[++i];
      }
    for (String s : Arrays.copyOfRange(args, 3, args.length))
      if (!Set.of("--stress", "--raw", "--freeze", "--external-paper").contains(s)
          && !s.equals(freezePath)) throw new IllegalArgumentException("Unknown option " + s);
    var mapper = new ObjectMapper().findAndRegisterModules();
    ResearchConfig cfg = mapper.readValue(Files.readString(Path.of(args[2])), ResearchConfig.class);
    if (Arrays.asList(args).contains("--stress")) cfg = cfg.stress();
    var limits =
        new AccountLedger.Limits(
            new BigDecimal("25"),
            new BigDecimal("25"),
            new BigDecimal("250"),
            new BigDecimal("25"),
            new BigDecimal("50"));
    if (Arrays.asList(args).contains("--external-paper")) {
      if (freezePath != null)
        throw new IllegalArgumentException(
            "External intent replay cannot qualify a frozen independent experiment");
      ClosedLoopReplay.runExternal(
          Path.of(args[0]),
          Path.of(args[1]),
          cfg,
          limits,
          mapper,
          Arrays.asList(args).contains("--raw"));
    } else if (freezePath == null)
      ClosedLoopReplay.run(
          Path.of(args[0]),
          Path.of(args[1]),
          cfg,
          limits,
          mapper,
          Arrays.asList(args).contains("--raw"));
    else {
      var frozen = mapper.readTree(Files.readString(Path.of(freezePath)));
      long start = java.time.Instant.parse(frozen.path("holdoutStart").asText()).toEpochMilli(),
          end = java.time.Instant.parse(frozen.path("holdoutEnd").asText()).toEpochMilli();
      ClosedLoopReplay.run(
          Path.of(args[0]),
          Path.of(args[1]),
          cfg,
          limits,
          mapper,
          Arrays.asList(args).contains("--raw"),
          start,
          end,
          ClosedLoopReplay.sha256(Path.of(freezePath)));
    }
    System.out.println("Closed-loop report: " + Path.of(args[1]).resolve("report.json"));
  }
}
