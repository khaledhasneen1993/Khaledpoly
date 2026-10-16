package com.polybot.hft.polymarket.ws;

import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;

/** Bounded single decoder. Never interrupts a disk writer during orderly drain. */
public final class MarketFrameQueue implements AutoCloseable {
  private final long maximumBytes;
  private final AtomicLong bytes = new AtomicLong();
  private final ThreadPoolExecutor worker;

  public MarketFrameQueue(int frames, long maximumBytes) {
    this.maximumBytes = maximumBytes;
    worker =
        new ThreadPoolExecutor(
            1,
            1,
            0,
            TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(frames),
            r -> {
              Thread t = new Thread(r, "clob-market-decoder");
              t.setDaemon(true);
              return t;
            },
            new ThreadPoolExecutor.AbortPolicy());
  }

  public boolean offer(long frameBytes, Runnable task) {
    if (frameBytes < 0 || frameBytes > maximumBytes) return false;
    long previous;
    do {
      previous = bytes.get();
      if (previous > maximumBytes - frameBytes) return false;
    } while (!bytes.compareAndSet(previous, previous + frameBytes));
    try {
      worker.execute(
          () -> {
            try {
              task.run();
            } finally {
              bytes.addAndGet(-frameBytes);
            }
          });
      return true;
    } catch (RejectedExecutionException rejected) {
      bytes.addAndGet(-frameBytes);
      return false;
    }
  }

  public int pendingFrames() {
    return worker.getQueue().size();
  }

  public long pendingBytes() {
    return bytes.get();
  }

  @Override
  public void close() {
    worker.shutdown();
    try {
      if (!worker.awaitTermination(10, TimeUnit.SECONDS))
        throw new IllegalStateException("Market decoder did not drain; recording is incomplete");
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException("Interrupted while draining market decoder", e);
    }
  }
}
