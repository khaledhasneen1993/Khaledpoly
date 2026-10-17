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
  void compressedTapePreservesLogicalRecordsAndHasFinalGzipTrailer() throws Exception {
    try (var journal=new PaperJournal(mapper,Clock.fixed(Instant.ofEpochMilli(1000),ZoneOffset.UTC),dir.toString(),"compressed","abc",true)) {
      for (int i=0;i<100;i++) journal.record("TICK",null,Map.of("payload","same payload ".repeat(100)));
    }
    Path path;
    try (var files=Files.walk(dir)) { path=files.filter(p->p.toString().endsWith("events.jsonl.gz")).findFirst().orElseThrow(); }
    try (var reader=TapeIO.reader(path)) {
      var rows=reader.lines().toList();
      assertThat(rows).hasSize(101);
      assertThat(mapper.readTree(rows.getLast()).path("kind").asText()).isEqualTo("RUN_END");
      for (int i=0;i<rows.size();i++) assertThat(mapper.readTree(rows.get(i)).path("seq").asLong()).isEqualTo(i+1);
      assertThat(Files.size(path)).isLessThan(rows.stream().mapToLong(String::length).sum());
    }
  }

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

  @Test
  void groupsCommitsButIdleFlushAndClosePersistAllRows() throws Exception {
    var j = new PaperJournal(mapper, Clock.systemUTC(), dir.toString(), "batch", "abc");
    for (int i = 0; i < 1000; i++) j.record("TICK", null, Map.of("i", i));
    assertThat(((Number) j.stats().get("commits")).longValue()).isLessThan(1000);
    // Deterministically invoke the same idle timer operation; no scheduler timing assertion.
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(j, "scheduledCommit");
    assertThat(j.stats().get("pendingBytes")).isEqualTo(0L);
    j.close();
    j.close();
    Path tape;
    try (var paths = Files.walk(dir)) {
      tape = paths.filter(p -> p.toString().endsWith("events.jsonl")).findFirst().orElseThrow();
    }
    var rows = Files.readAllLines(tape);
    assertThat(rows).hasSize(1001);
    for (int i = 0; i < rows.size(); i++)
      assertThat(mapper.readTree(rows.get(i)).path("seq").asInt()).isEqualTo(i + 1);
    assertThatThrownBy(() -> j.record("LATE", null, Map.of())).hasMessageContaining("closed");
  }

  @Test
  void backgroundCommitFailureLatchesAndNeverWritesCleanEnd() throws Exception {
    var j = new PaperJournal(mapper, Clock.systemUTC(), dir.toString(), "failure", "abc");
    j.record("TICK", null, Map.of());
    ((java.nio.channels.FileChannel)
            org.springframework.test.util.ReflectionTestUtils.getField(j, "file"))
        .close();
    org.springframework.test.util.ReflectionTestUtils.setField(j, "pendingBytes", 1L);
    org.springframework.test.util.ReflectionTestUtils.invokeMethod(j, "scheduledCommit");
    assertThat(j.stats().get("failed")).isEqualTo(true);
    assertThatThrownBy(() -> j.record("LATE", null, Map.of())).hasMessageContaining("failed");
    j.close();
    try (var paths = Files.walk(dir)) {
      Path tape =
          paths.filter(p -> p.toString().endsWith("events.jsonl")).findFirst().orElseThrow();
      assertThat(Files.readString(tape)).doesNotContain("RUN_END");
    }
  }

  @Test
  void concurrentProducersRetainOneContiguousCausalSequence() throws Exception {
    try (var j = new PaperJournal(mapper, Clock.systemUTC(), dir.toString(), "concurrent", "abc");
        var pool = java.util.concurrent.Executors.newFixedThreadPool(4)) {
      var tasks = new ArrayList<java.util.concurrent.Future<?>>();
      for (int t = 0; t < 4; t++)
        tasks.add(
            pool.submit(
                () -> {
                  for (int i = 0; i < 200; i++) j.record("TICK", null, Map.of("i", i));
                }));
      for (var task : tasks) task.get();
    }
    try (var paths = Files.walk(dir)) {
      Path tape =
          paths.filter(p -> p.toString().endsWith("events.jsonl")).findFirst().orElseThrow();
      var rows = Files.readAllLines(tape);
      assertThat(rows).hasSize(801);
      for (int i = 0; i < rows.size(); i++)
        assertThat(mapper.readTree(rows.get(i)).path("seq").asInt()).isEqualTo(i + 1);
    }
  }
}
