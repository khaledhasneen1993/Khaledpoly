package com.polybot.hft.paper;

import com.polybot.hft.events.HftEventPublisher;
import java.time.Instant;
import java.util.Map;

public record RecordingEventPublisher(HftEventPublisher delegate, PaperJournal journal)
    implements HftEventPublisher {
  public boolean isEnabled() {
    return delegate.isEnabled() || journal.enabled();
  }

  public void publish(Instant ts, String type, String key, Object data) {
    journal.record(
        "APPLICATION_EVENT",
        ts == null ? null : ts.toEpochMilli(),
        Map.of("type", type, "key", key == null ? "" : key, "payload", data));
    if (delegate.isEnabled()) delegate.publish(ts, type, key, data);
  }
}
