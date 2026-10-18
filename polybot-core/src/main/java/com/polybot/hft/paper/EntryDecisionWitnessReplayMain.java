package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;

/** Explicit offline witness CLI: no service flag, independent mode or real execution. */
public final class EntryDecisionWitnessReplayMain {
  public static void main(String[] args) throws Exception {
    if (args.length!=5) throw new IllegalArgumentException("Usage: entry-witness TAPE NEW-OUT CONFIG LABELS WINDOWS");
    var mapper=new ObjectMapper().findAndRegisterModules();
    var spec=mapper.readTree(Files.readString(Path.of(args[4])));
    if (!spec.isArray()) throw new IllegalArgumentException("Require window array");
    var windows=new ArrayList<EntryDecisionWitness.Window>();
    for(var row:spec) {
      if(!row.path("condition").isTextual() || !row.path("startMs").isIntegralNumber() || !row.path("endMs").isIntegralNumber())
        throw new IllegalArgumentException("Malformed witness window");
      windows.add(new EntryDecisionWitness.Window(row.get("condition").textValue(),row.get("startMs").longValue(),row.get("endMs").longValue()));
    }
    var witness=new EntryDecisionWitness(windows);
    var config=mapper.readValue(Files.readString(Path.of(args[2])),ResearchConfig.class);
    var limits=new AccountLedger.Limits(new BigDecimal("25"),new BigDecimal("25"),new BigDecimal("250"),new BigDecimal("25"),new BigDecimal("50"));
    ClosedLoopReplay.runDecisionWitnessLab(Path.of(args[0]),Path.of(args[1]),config,limits,mapper,
        SettlementReplayLabels.load(Path.of(args[3]),mapper),witness);
  }
}
