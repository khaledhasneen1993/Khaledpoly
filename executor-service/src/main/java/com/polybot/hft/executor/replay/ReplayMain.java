package com.polybot.hft.executor.replay;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.paper.ReplayRunner;
import java.nio.file.*;

public final class ReplayMain {
  public static void main(String[] args) throws Exception {
    if (args.length < 2 || args.length > 3)
      throw new IllegalArgumentException(
          "Usage: replay events.jsonl NEW-output-directory [--stress]");
    if (args.length == 3 && !args[2].equals("--stress"))
      throw new IllegalArgumentException("Unknown option");
    Path out = Path.of(args[1]);
    if (Files.exists(out)) throw new IllegalArgumentException("Output directory must not exist");
    var mapper = new ObjectMapper().findAndRegisterModules();
    var report = ReplayRunner.run(Path.of(args[0]), out, args.length == 3, mapper);
    Files.writeString(
        out.resolve("report.json"),
        mapper.writerWithDefaultPrettyPrinter().writeValueAsString(report),
        StandardOpenOption.CREATE_NEW);
    System.out.println(
        "Replay saved: "
            + out.resolve("report.json")
            + "; decision=NO_GO (research validation required)");
  }
}
