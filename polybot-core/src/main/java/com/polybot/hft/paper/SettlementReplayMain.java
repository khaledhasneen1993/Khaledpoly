package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;

/** Separate explicit offline CLI. No service property/endpoint or independent/holdout mode. */
public final class SettlementReplayMain {
  public static void main(String[] args) throws Exception {
    if (args.length!=4) throw new IllegalArgumentException("Usage: settlement-lab TAPE NEW-OUT CONFIG LABELS");
    var mapper=new ObjectMapper().findAndRegisterModules();
    var config=mapper.readValue(Files.readString(Path.of(args[2])),ResearchConfig.class);
    var limits=new AccountLedger.Limits(new BigDecimal("25"),new BigDecimal("25"),
        new BigDecimal("250"),new BigDecimal("25"),new BigDecimal("50"));
    ClosedLoopReplay.runSettlementLab(Path.of(args[0]),Path.of(args[1]),config,limits,mapper,
        SettlementReplayLabels.load(Path.of(args[3]),mapper));
  }
}
