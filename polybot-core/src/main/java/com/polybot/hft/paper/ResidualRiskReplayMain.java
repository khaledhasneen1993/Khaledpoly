package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;

/** Explicit offline comparison CLI only. No service property or live/independent mode. */
public final class ResidualRiskReplayMain {
  public static void main(String[] args) throws Exception {
    if (args.length!=5 || !(args[4].equals("control") || args[4].equals("candidate")))
      throw new IllegalArgumentException("Usage: residual-risk-lab TAPE NEW-OUT CONFIG LABELS control|candidate");
    var mapper=new ObjectMapper().findAndRegisterModules();
    var config=mapper.readValue(Files.readString(Path.of(args[2])),ResearchConfig.class);
    var limits=new AccountLedger.Limits(new BigDecimal("25"),new BigDecimal("25"),
        new BigDecimal("250"),new BigDecimal("25"),new BigDecimal("50"));
    ClosedLoopReplay.runResidualRiskLab(Path.of(args[0]),Path.of(args[1]),config,limits,mapper,
        SettlementReplayLabels.load(Path.of(args[3]),mapper),args[4].equals("candidate"));
  }
}
