package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.time.Clock;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** Append-only local tape. Failures propagate: an incomplete experiment must not look valid. */
@Component
public class PaperJournal implements AutoCloseable {
  private final ObjectMapper mapper;
  private final Clock clock;
  private final String runId = UUID.randomUUID().toString();
  private final long origin = System.nanoTime();
  private long seq;
  private FileChannel file;
  private boolean failed;

  public PaperJournal(
      ObjectMapper mapper,
      Clock clock,
      @Value("${paper.record.directory:}") String directory,
      @Value("${spring.application.name:app}") String service,
      @Value("${paper.record.revision:unrecorded}") String revision) {
    this.mapper = mapper;
    this.clock = clock;
    if (directory.isBlank()) return;
    try {
      Path run = Path.of(directory).resolve(service + "-" + runId);
      Files.createDirectories(run);
      try {
        Files.setPosixFilePermissions(
            run, java.nio.file.attribute.PosixFilePermissions.fromString("rwx------"));
      } catch (UnsupportedOperationException ignored) {
      }
      Files.writeString(
          run.resolve("manifest.json"),
          mapper
              .writerWithDefaultPrettyPrinter()
              .writeValueAsString(
                  Map.of(
                      "schema",
                      1,
                      "runId",
                      runId,
                      "service",
                      service,
                      "revision",
                      revision,
                      "startedAt",
                      clock.instant().toString(),
                      "purpose",
                      "PAPER research; public queue position is unknown",
                      "matchingModel",
                      "conservative-l2-v1")),
          StandardOpenOption.CREATE_NEW);
      file =
          FileChannel.open(
              run.resolve("events.jsonl"), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    } catch (IOException e) {
      throw new IllegalStateException("Cannot open paper tape", e);
    }
  }

  public boolean enabled() {
    return file != null;
  }

  public synchronized long record(String kind, Long sourceMs, Object data) {
    if (failed) throw new IllegalStateException("Paper tape failed; restart required");
    long at = clock.millis();
    if (file == null) return at;
    try {
      var row = new LinkedHashMap<String, Object>();
      row.put("schema", 1);
      row.put("runId", runId);
      row.put("seq", ++seq);
      row.put("arrivalMs", at);
      row.put("elapsedNanos", System.nanoTime() - origin);
      row.put("kind", kind);
      row.put("sourceMs", sourceMs);
      row.put("data", data);
      byte[] bytes =
          (mapper.writeValueAsString(row) + "\n").getBytes(java.nio.charset.StandardCharsets.UTF_8);
      var buffer = java.nio.ByteBuffer.wrap(bytes);
      while (buffer.hasRemaining()) file.write(buffer);
      file.force(false);
      return at;
    } catch (IOException e) {
      failed = true;
      throw new IllegalStateException("Paper tape write failed", e);
    }
  }

  @PreDestroy
  public synchronized void close() {
    if (file != null)
      try {
        if (file.isOpen() && !failed) record("RUN_END", null, Map.of("complete", true));
        file.close();
      } catch (IOException e) {
        throw new IllegalStateException(e);
      }
  }
}
