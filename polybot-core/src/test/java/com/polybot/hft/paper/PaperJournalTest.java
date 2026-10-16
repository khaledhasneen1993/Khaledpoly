package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class PaperJournalTest {
  @TempDir Path dir;
  final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();

  @Test
  void recordsReceiveOrderSourceClockAndCleanEnd() throws Exception {
    try (var j =
        new PaperJournal(
            mapper,
            Clock.fixed(Instant.ofEpochMilli(1000), ZoneOffset.UTC),
            dir.toString(),
            "test",
            "abc")) {
      j.record("RAW_MARKET", 990L, Map.of("text", "example"));
      j.record("MATCH_TICK", null, Map.of());
    }
    Path tape;
    try (var files = Files.walk(dir)) {
      tape =
          files
              .filter(p -> p.getFileName().toString().equals("events.jsonl"))
              .findFirst()
              .orElseThrow();
    }
    var lines = Files.readAllLines(tape);
    assertThat(lines).hasSize(3);
    assertThat(mapper.readTree(lines.get(0)).path("sourceMs").asLong()).isEqualTo(990);
    assertThat(mapper.readTree(lines.get(2)).path("kind").asText()).isEqualTo("RUN_END");
    assertThat(mapper.readTree(lines.get(2)).path("seq").asLong()).isEqualTo(3);
  }

  @Test
  void sequenceGapsAndMixedRunsRejectReplay() throws Exception {
    Path tape = dir.resolve("bad.jsonl");
    Files.writeString(
        tape, "{\"schema\":1,\"seq\":2,\"runId\":\"a\",\"arrivalMs\":100,\"kind\":\"X\"}\n");
    assertThatThrownBy(() -> ReplayRunner.run(tape, dir.resolve("out"), false, mapper))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("sequence");
  }
}
