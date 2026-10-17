package com.polybot.hft.paper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Reproducible latency stress assumptions; never inferred venue measurements. */
public record LatencyProfile(long baseMs, long jitterMs, long seed) {
  public LatencyProfile {
    if (baseMs < 0 || jitterMs < 0 || jitterMs > 60000)
      throw new IllegalArgumentException("Invalid latency profile");
  }

  public long delay(String action, String id) {
    if (jitterMs == 0) return baseMs;
    try {
      byte[] hash =
          MessageDigest.getInstance("SHA-256")
              .digest((action + ":" + id).getBytes(StandardCharsets.UTF_8));
      long bits = java.nio.ByteBuffer.wrap(hash).getLong() ^ seed;
      return Math.addExact(baseMs, Math.floorMod(bits, jitterMs + 1));
    } catch (java.security.NoSuchAlgorithmException e) {
      throw new IllegalStateException(e);
    }
  }
}
