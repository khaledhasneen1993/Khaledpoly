package com.polybot.hft.polymarket.ws;

import java.util.*;
import java.util.concurrent.CompletionStage;
import java.util.function.Supplier;

/** Per-connection diagnostics only. Text PONG has no ID: ambiguous replies never claim an RTT. */
public final class HeartbeatProbe {
  private long attempts, sent, failed, replies, pendingSends, outstandingReplies, ambiguousReplies;
  private long lastAttemptMs, lastReplyMs, lastAttemptNanos, maxAttemptGapMicros, maxSendMicros;
  private long lastUnambiguousReplyMicros = -1;
  private boolean correlationLost;

  public void ping(long atMs, long atNanos, Supplier<? extends CompletionStage<?>> send) {
    synchronized (this) {
      attempts++;
      pendingSends++;
      outstandingReplies++;
      if (lastAttemptNanos != 0)
        maxAttemptGapMicros = Math.max(maxAttemptGapMicros, (atNanos - lastAttemptNanos) / 1000);
      lastAttemptMs = atMs;
      lastAttemptNanos = atNanos;
    }
    try {
      send.get().whenComplete((ignored, error) -> complete(atNanos, error));
    } catch (RuntimeException error) {
      complete(atNanos, error);
    }
  }

  private synchronized void complete(long startedNanos, Throwable error) {
    pendingSends--;
    maxSendMicros = Math.max(maxSendMicros, (System.nanoTime() - startedNanos) / 1000);
    if (error == null) sent++;
    else {
      failed++;
      correlationLost = true;
    }
  }

  public synchronized void pong(long atMs, long atNanos) {
    replies++;
    lastReplyMs = atMs;
    if (outstandingReplies == 1 && !correlationLost)
      lastUnambiguousReplyMicros = Math.max(0, (atNanos - lastAttemptNanos) / 1000);
    else {
      ambiguousReplies++;
      lastUnambiguousReplyMicros = -1;
      correlationLost = true;
    }
    outstandingReplies = Math.max(0, outstandingReplies - 1);
  }

  public synchronized Map<String, Object> snapshot() {
    var m = new LinkedHashMap<String, Object>();
    m.put("pingAttempts", attempts);
    m.put("pingSendsCompleted", sent);
    m.put("pingSendsFailed", failed);
    m.put("pendingPingSends", pendingSends);
    m.put("unansweredPings", outstandingReplies);
    m.put("textPongs", replies);
    m.put("ambiguousPongs", ambiguousReplies);
    m.put("lastPingMs", lastAttemptMs);
    m.put("lastPongMs", lastReplyMs);
    m.put("maxPingAttemptGapMicros", maxAttemptGapMicros);
    m.put("maxPingSendMicros", maxSendMicros);
    m.put("lastUnambiguousPongMicros", lastUnambiguousReplyMicros);
    return Map.copyOf(m);
  }
}
