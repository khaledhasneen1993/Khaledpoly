package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class AlertOutboxTest {
  @TempDir Path dir;

  @Test
  void dedupRetryAndAcknowledgementSurviveRestart() {
    Path path = dir.resolve("alerts.json");
    var mapper = new ObjectMapper().findAndRegisterModules();
    try (var out = new PaperAlertOutbox(path, mapper)) {
      out.add("risk", "Exposure", 1000);
      out.add("risk", "Exposure", 1001);
      assertThat(out.pending(1001)).hasSize(1);
      out.acknowledge("risk", false, 1001);
      assertThat(out.pending(1002)).isEmpty();
    }
    try (var out = new PaperAlertOutbox(path, mapper)) {
      assertThat(out.pending(10000))
          .singleElement()
          .satisfies(a -> assertThat(a.suppressed()).isEqualTo(1));
      out.acknowledge("risk", true, 10000);
      assertThat(out.pending(10001)).isEmpty();
    }
  }

  @Test
  void honorsVenueRetryAfterLongerThanLocalBackoff() {
    assertThat(ResearchFeed.retryDeadline("120", 1000)).isEqualTo(121000);
    assertThat(ResearchFeed.retryDeadline("invalid", 1000)).isEqualTo(61000);
    assertThat(ResearchFeed.retryDeadline("Thu, 01 Jan 1970 00:02:00 GMT", 1000)).isEqualTo(120000);
  }
}
