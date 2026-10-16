package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.state.AtomicJsonState;
import java.nio.file.Path;
import java.util.*;

/** Durable local alerts. Delivery acknowledgement is explicit; duplicate keys are throttled. */
public final class PaperAlertOutbox implements AutoCloseable {
  public record Alert(
      String key,
      String message,
      long at,
      int attempts,
      long retryAt,
      boolean delivered,
      long suppressed) {}

  private final AtomicJsonState file;
  private final Map<String, Alert> alerts = new TreeMap<>();

  public PaperAlertOutbox(Path path, ObjectMapper mapper) {
    file = new AtomicJsonState(path, mapper);
    var saved = file.load();
    if (saved != null)
      saved
          .fields()
          .forEachRemaining(
              e -> alerts.put(e.getKey(), mapper.convertValue(e.getValue(), Alert.class)));
  }

  public synchronized void add(String key, String message, long at) {
    var old = alerts.get(key);
    if (old != null && (!old.delivered() || at - old.at() < 300000)) {
      alerts.put(
          key,
          new Alert(
              old.key(),
              old.message(),
              old.at(),
              old.attempts(),
              old.retryAt(),
              old.delivered(),
              old.suppressed() + 1));
    } else {
      if (alerts.size() >= 1000) {
        alerts
            .entrySet()
            .removeIf(e -> e.getValue().delivered() && at - e.getValue().at() > 86400000);
        if (alerts.size() >= 1000) throw new IllegalStateException("Alert outbox full");
      }
      alerts.put(key, new Alert(key, message, at, 0, at, false, 0));
    }
    file.save(alerts);
  }

  public synchronized List<Alert> pending(long now) {
    return alerts.values().stream().filter(a -> !a.delivered() && now >= a.retryAt()).toList();
  }

  public synchronized List<Alert> snapshot() {
    return List.copyOf(alerts.values());
  }

  public synchronized void acknowledge(String key, boolean success, long now) {
    var a = alerts.get(key);
    if (a == null) return;
    int count = a.attempts() + 1;
    alerts.put(
        key,
        new Alert(
            key,
            a.message(),
            a.at(),
            count,
            now + Math.min(3600000, 1000L << Math.min(count, 12)),
            success,
            a.suppressed()));
    file.save(alerts);
  }

  public synchronized void close() {
    file.close();
  }
}
