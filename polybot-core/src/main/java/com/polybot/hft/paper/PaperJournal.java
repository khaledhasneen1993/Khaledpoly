package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import java.io.*;
import java.nio.channels.Channels;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.time.Clock;
import java.util.*;
import java.util.concurrent.*;
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
  // Research observations may be group-committed. AccountLedger remains independently fsynced.
  static final long COMMIT_MILLIS = 25;
  static final int COMMIT_BYTES = 256 * 1024;
  private BufferedOutputStream output;
  private ScheduledExecutorService flusher;
  private long pendingBytes, lastCommitNanos = System.nanoTime(), commits, writtenBytes;
  private long maxCommitMicros, maxAppendMicros;
  private boolean failed, closed;

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
                      "durability",
                      Map.of(
                          "policy",
                          "group-commit-v1",
                          "intervalMs",
                          COMMIT_MILLIS,
                          "batchThresholdBytes",
                          COMMIT_BYTES,
                          "requiresCleanRunEnd",
                          true),
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
      output = new BufferedOutputStream(Channels.newOutputStream(file), COMMIT_BYTES);
      flusher =
          Executors.newSingleThreadScheduledExecutor(
              r -> {
                Thread t = new Thread(r, "paper-tape-commit");
                t.setDaemon(true);
                return t;
              });
      flusher.scheduleWithFixedDelay(
          this::scheduledCommit, COMMIT_MILLIS, COMMIT_MILLIS, TimeUnit.MILLISECONDS);
    } catch (IOException e) {
      throw new IllegalStateException("Cannot open paper tape", e);
    }
  }

  public boolean enabled() {
    return file != null;
  }

  public synchronized long record(String kind, Long sourceMs, Object data) {
    if (failed) throw new IllegalStateException("Paper tape failed; restart required");
    if (closed) throw new IllegalStateException("Paper tape is closed");
    long started = System.nanoTime();
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
      output.write(bytes);
      writtenBytes += bytes.length;
      pendingBytes += bytes.length;
      if (pendingBytes >= COMMIT_BYTES
          || System.nanoTime() - lastCommitNanos >= COMMIT_MILLIS * 1_000_000L) commit();
      maxAppendMicros = Math.max(maxAppendMicros, (System.nanoTime() - started) / 1000);
      return at;
    } catch (IOException e) {
      failed = true;
      throw new IllegalStateException("Paper tape write failed", e);
    }
  }

  private void commit() throws IOException {
    if (pendingBytes == 0) return;
    long started = System.nanoTime();
    output.flush();
    file.force(false);
    pendingBytes = 0;
    lastCommitNanos = System.nanoTime();
    commits++;
    maxCommitMicros = Math.max(maxCommitMicros, (lastCommitNanos - started) / 1000);
  }

  private synchronized void scheduledCommit() {
    if (closed || failed) return;
    try {
      commit();
    } catch (IOException e) {
      // The next producer fails closed; close will never attest a clean end.
      failed = true;
    }
  }

  public synchronized Map<String, Object> stats() {
    return Map.of(
        "records",
        seq,
        "writtenBytes",
        writtenBytes,
        "pendingBytes",
        pendingBytes,
        "commits",
        commits,
        "maxCommitMicros",
        maxCommitMicros,
        "maxAppendMicros",
        maxAppendMicros,
        "failed",
        failed);
  }

  @PreDestroy
  public synchronized void close() {
    if (closed) return;
    if (flusher != null) flusher.shutdownNow();
    try {
      if (file != null && file.isOpen()) {
        if (failed) throw new IOException("Paper tape failed; no clean RUN_END");
        record("RUN_END", null, Map.of("complete", true));
        commit();
      }
    } catch (IOException e) {
      failed = true;
      throw new IllegalStateException("Cannot finalize paper tape", e);
    } finally {
      closed = true;
      if (file != null) {
        try {
          file.close();
        } catch (IOException e) {
          failed = true;
          throw new IllegalStateException("Cannot close paper tape", e);
        }
      }
    }
  }
}
