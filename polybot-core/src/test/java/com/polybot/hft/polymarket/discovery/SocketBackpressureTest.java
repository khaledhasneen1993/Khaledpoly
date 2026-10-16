package com.polybot.hft.polymarket.discovery;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.paper.PaperJournal;
import java.net.http.WebSocket;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.springframework.test.util.ReflectionTestUtils;

class SocketBackpressureTest {
  @Test
  @Timeout(10)
  void queuedFramesKeepCallbackClocksAndStaleDataCannotBecomeFresh() throws Exception {
    var helper = new WebSocketFreshnessTest();
    var clock = new WebSocketFreshnessTest.MutableClock();
    var client = helper.client(clock);
    var socket = mock(WebSocket.class);
    ReflectionTestUtils.setField(client, "webSocket", socket);
    var entered = new CountDownLatch(1);
    var release = new CountDownLatch(1);
    var first = new AtomicBoolean(true);
    var receipts = new CopyOnWriteArrayList<Long>();
    var gaps = new CopyOnWriteArrayList<JsonNode>();
    client.onTape(
        (k, n) -> {
          if (k.equals("GAP")) gaps.add(n);
        });
    var recorder =
        new PaperJournal(new ObjectMapper(), clock, "", "test", "abc") {
          @Override
          public synchronized long record(String kind, Long source, Object data) {
            if (kind.equals("RAW_MARKET")) {
              receipts.add((Long) ((Map<?, ?>) data).get("callbackReceivedMs"));
              if (first.getAndSet(false)) {
                entered.countDown();
                try {
                  if (!release.await(3, TimeUnit.SECONDS))
                    throw new AssertionError("producer blocked");
                } catch (InterruptedException e) {
                  throw new AssertionError(e);
                }
              }
            }
            return clock.millis();
          }
        };
    ReflectionTestUtils.setField(client, "journal", recorder);
    long at = clock.millis();
    try {
      ReflectionTestUtils.invokeMethod(
          client, "enqueueFrame", socket, helper.book(at, "0.5"), at, System.nanoTime());
      assertThat(entered.await(3, TimeUnit.SECONDS)).isTrue();
      clock.now = clock.now.plusSeconds(3);
      ReflectionTestUtils.invokeMethod(
          client,
          "enqueueFrame",
          socket,
          helper.book(at + 3000, "0.4"),
          at + 3000,
          System.nanoTime());
    } finally {
      release.countDown();
      client.stopAndDrainFrames();
    }
    assertThat(receipts).containsExactly(at, at + 3000);
    assertThat(gaps).hasSize(1);
    assertThat(gaps.getFirst().path("reason").asText()).isEqualTo("stale_source");
    assertThat(gaps.getFirst().path("processingAgeMs").asLong()).isEqualTo(3000);
    assertThat(client.getTopOfBook("123").orElseThrow().bestBid()).isEqualByComparingTo("0.4");
  }

  @Test
  @Timeout(10)
  void overflowBlocksBookImmediatelyAndEmitsExplicitGapWithoutProcessingRejectedFrame()
      throws Exception {
    var helper = new WebSocketFreshnessTest();
    var clock = new WebSocketFreshnessTest.MutableClock();
    var client = helper.client(clock);
    var socket = mock(WebSocket.class);
    ReflectionTestUtils.setField(client, "webSocket", socket);
    ReflectionTestUtils.invokeMethod(client, "handleMessage", helper.book(clock.millis(), "0.5"));
    assertThat(client.getTopOfBook("123")).isPresent();
    var entered = new CountDownLatch(1);
    var release = new CountDownLatch(1);
    var gap = new CountDownLatch(1);
    client.onTape(
        (k, n) -> {
          if (k.equals("GAP") && n.path("reason").asText().equals("decoder_overflow"))
            gap.countDown();
        });
    var q =
        (com.polybot.hft.polymarket.ws.MarketFrameQueue)
            ReflectionTestUtils.getField(client, "frames");
    try {
      assertThat(
              q.offer(
                  8L * 1024 * 1024,
                  () -> {
                    entered.countDown();
                    try {
                      release.await(3, TimeUnit.SECONDS);
                    } catch (InterruptedException e) {
                      throw new AssertionError(e);
                    }
                  }))
          .isTrue();
      assertThat(entered.await(3, TimeUnit.SECONDS)).isTrue();
      ReflectionTestUtils.invokeMethod(
          client,
          "enqueueFrame",
          socket,
          helper.book(clock.millis(), "0.4"),
          clock.millis(),
          System.nanoTime());
      assertThat(client.getTopOfBook("123")).isEmpty();
      assertThat(gap.await(3, TimeUnit.SECONDS)).isTrue();
    } finally {
      release.countDown();
      ReflectionTestUtils.invokeMethod(client, "shutdown");
    }
  }

  @Test
  @Timeout(10)
  void subscriptionReconnectDoesNotWaitWhileAnExternalCallerCouldOwnTheSimulatorMonitor()
      throws Exception {
    var helper = new WebSocketFreshnessTest();
    var client = helper.client(new WebSocketFreshnessTest.MutableClock());
    ReflectionTestUtils.setField(client, "httpClient", mock(java.net.http.HttpClient.class));
    Object decodeLock = ReflectionTestUtils.getField(client, "decodeLock");
    var entered = new CountDownLatch(1);
    var release = new CountDownLatch(1);
    try (var pool = Executors.newSingleThreadExecutor()) {
      var held =
          pool.submit(
              () -> {
                synchronized (decodeLock) {
                  entered.countDown();
                  try {
                    release.await(5, TimeUnit.SECONDS);
                  } catch (InterruptedException e) {
                    throw new AssertionError(e);
                  }
                }
              });
      assertThat(entered.await(3, TimeUnit.SECONDS)).isTrue();
      try {
        // The decode lock belongs to another thread; this only schedules recovery.
        ReflectionTestUtils.invokeMethod(client, "reconnectLocked");
        assertThat(release.getCount()).isEqualTo(1);
      } finally {
        ReflectionTestUtils.setField(client, "stopping", true);
        release.countDown();
        held.get(3, TimeUnit.SECONDS);
        ReflectionTestUtils.invokeMethod(client, "shutdown");
      }
    }
  }
}
