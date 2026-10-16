package com.polybot.hft.polymarket.discovery;

import static org.assertj.core.api.Assertions.*;

import com.polybot.hft.polymarket.ws.MarketFrameQueue;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;

class MarketFrameQueueTest {
  void await(CountDownLatch latch) {
    try {
      if (!latch.await(3, TimeUnit.SECONDS)) throw new AssertionError("decoder blocked");
    } catch (InterruptedException e) {
      throw new AssertionError("writer interrupted", e);
    }
  }

  @Test
  void producerDoesNotWaitForDecoderAndAcceptedFramesDrainInReceiveOrder() {
    var release = new CountDownLatch(1);
    var entered = new CountDownLatch(1);
    var order = new CopyOnWriteArrayList<Integer>();
    var q = new MarketFrameQueue(4, 100);
    try {
      assertThat(
              q.offer(
                  10,
                  () -> {
                    order.add(1);
                    entered.countDown();
                    await(release);
                  }))
          .isTrue();
      await(entered);
      assertThat(q.offer(10, () -> order.add(2))).isTrue();
      assertThat(q.offer(10, () -> order.add(3))).isTrue();
      assertThat(order).containsExactly(1);
      assertThat(q.pendingBytes()).isEqualTo(30);
    } finally {
      release.countDown();
      q.close();
    }
    assertThat(order).containsExactly(1, 2, 3);
    assertThat(q.pendingBytes()).isZero();
    assertThat(q.offer(1, () -> order.add(4))).isFalse();
  }

  @Test
  void byteBudgetRejectsOverflowWithoutExecutingOrLeakingReservations() {
    var release = new CountDownLatch(1);
    var entered = new CountDownLatch(1);
    var rejectedRan = new AtomicBoolean();
    var q = new MarketFrameQueue(4, 16);
    try {
      assertThat(
              q.offer(
                  8,
                  () -> {
                    entered.countDown();
                    await(release);
                  }))
          .isTrue();
      await(entered);
      assertThat(q.offer(8, () -> {})).isTrue();
      assertThat(q.offer(1, () -> rejectedRan.set(true))).isFalse();
      assertThat(q.offer(17, () -> rejectedRan.set(true))).isFalse();
      assertThat(q.pendingBytes()).isEqualTo(16);
    } finally {
      release.countDown();
      q.close();
    }
    assertThat(rejectedRan).isFalse();
    assertThat(q.pendingBytes()).isZero();
  }

  @Test
  void frameCountBudgetIsIndependentOfByteBudget() {
    var release = new CountDownLatch(1);
    var entered = new CountDownLatch(1);
    var q = new MarketFrameQueue(1, 100);
    try {
      assertThat(
              q.offer(
                  1,
                  () -> {
                    entered.countDown();
                    await(release);
                  }))
          .isTrue();
      await(entered);
      assertThat(q.offer(1, () -> {})).isTrue();
      assertThat(q.offer(1, () -> fail("rejected frame executed"))).isFalse();
      assertThat(q.pendingBytes()).isEqualTo(2);
      assertThat(q.pendingFrames()).isEqualTo(1);
    } finally {
      release.countDown();
      q.close();
    }
    assertThat(q.pendingBytes()).isZero();
  }
}
