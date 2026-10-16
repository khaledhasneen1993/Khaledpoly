package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class PaperMetricsTest {
  final ObjectMapper mapper = new ObjectMapper();

  JsonNode book(long source) {
    return mapper.valueToTree(
        Map.of(
            "token",
            "u",
            "sourceMs",
            source,
            "bids",
            List.of(Map.of("price", "0.5", "size", "10")),
            "asks",
            List.of(Map.of("price", "0.6", "size", "10"))));
  }

  @Test
  void markoutUsesOnlyFutureFreshObservationsAndPreservesMissingHorizon() {
    var m = new PaperMetrics();
    m.fill(
        new PaperMatchingEngine.Fill(
            "a", "u", true, new BigDecimal("0.4"), new BigDecimal("2"), 1000));
    m.book(book(1500), 1500);
    assertThat((Map<?, ?>) m.snapshot(1500).get("markoutSamples")).isEmpty();
    m.book(book(1999), 2000);
    assertThat((Map<?, ?>) m.snapshot(2000).get("markoutSamples")).isEmpty();
    m.book(book(2100), 2100);
    assertThat(((Map<?, ?>) m.snapshot(2100).get("markoutSamples")).containsKey(1000)).isTrue();
    assertThat((BigDecimal) ((Map<?, ?>) m.snapshot(2100).get("markoutPnl")).get(1000))
        .isEqualByComparingTo("0.30");
    m.book(book(10000), 10000);
    assertThat(((Map<?, ?>) m.snapshot(10000).get("markoutSamples")).containsKey(5000)).isFalse();
  }
}
