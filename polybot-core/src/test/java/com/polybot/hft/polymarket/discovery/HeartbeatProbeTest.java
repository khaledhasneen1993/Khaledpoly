package com.polybot.hft.polymarket.discovery;

import static org.assertj.core.api.Assertions.*;

import com.polybot.hft.polymarket.ws.HeartbeatProbe;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class HeartbeatProbeTest {
  @Test
  void tracksPendingSuccessAndUnambiguousReplyWithoutCallingSendCompletionAReply() {
    var p = new HeartbeatProbe();
    var send = new CompletableFuture<Void>();
    long n = System.nanoTime();
    p.ping(1000, n, () -> send);
    assertThat(p.snapshot().get("pendingPingSends")).isEqualTo(1L);
    send.complete(null);
    assertThat(p.snapshot().get("pingSendsCompleted")).isEqualTo(1L);
    assertThat(p.snapshot().get("textPongs")).isEqualTo(0L);
    p.pong(1001, n + 1_000_000);
    assertThat(p.snapshot().get("lastUnambiguousPongMicros")).isEqualTo(1000L);
    assertThat(p.snapshot().get("unansweredPings")).isEqualTo(0L);
  }

  @Test
  void failedSendAndUnidentifiableRepliesAreVisibleAndNeverClaimRtt() {
    var p = new HeartbeatProbe();
    long n = System.nanoTime();
    p.ping(1000, n, () -> CompletableFuture.failedFuture(new IllegalStateException("network")));
    p.ping(11000, n + 10_000_000_000L, () -> CompletableFuture.completedFuture(null));
    p.pong(11001, n + 10_001_000_000L);
    assertThat(p.snapshot().get("pingSendsFailed")).isEqualTo(1L);
    assertThat(p.snapshot().get("ambiguousPongs")).isEqualTo(1L);
    assertThat(p.snapshot().get("lastUnambiguousPongMicros")).isEqualTo(-1L);
    assertThat(p.snapshot().get("maxPingAttemptGapMicros")).isEqualTo(10_000_000L);
    p.ping(
        21000,
        n + 20_000_000_000L,
        () -> {
          throw new IllegalStateException("closed");
        });
    assertThat(p.snapshot().get("pingSendsFailed")).isEqualTo(2L);
    assertThat(p.snapshot().get("pendingPingSends")).isEqualTo(0L);
  }
}
