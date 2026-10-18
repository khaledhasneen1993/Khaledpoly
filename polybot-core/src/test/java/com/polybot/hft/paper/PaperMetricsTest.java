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

  void fill(PaperMetrics m, String id, String token) {
    m.fill(new PaperMatchingEngine.Fill(id, token, true, new BigDecimal("0.4"),
        new BigDecimal("2"), 1000));
  }

  @Test
  void scopedGapPermanentlyInvalidatesOnlyAffectedPendingHorizons() {
    var m = new PaperMetrics();
    fill(m, "a", "u");
    fill(m, "b", "v");
    m.gap(Set.of("u"));
    m.book(book(2100), 2100);
    var other = (com.fasterxml.jackson.databind.node.ObjectNode) book(2100);
    other.put("token", "v");
    m.book(other, 2100);
    assertThat((Map<?, ?>) m.snapshot(2100).get("markoutSamples"))
        .isEqualTo(Map.of(1000, 1));
    assertThat((Map<?, ?>) m.snapshot(2100).get("missingMarkoutsByReason"))
        .isEqualTo(Map.of("DATA_GAP", Map.of(1000, 1, 5000, 1, 30000, 1)));
    m.gap(Set.of("u")); // Repeated gaps must not double-count missing horizons.
    assertThat(m.snapshot(2100).get("pendingMarkouts")).isEqualTo(2);
  }

  @Test
  void globalGapPreservesCompletedHorizonButNeverResurrectsPendingOnRecovery() {
    var m = new PaperMetrics();
    fill(m, "a", "u");
    m.book(book(2100), 2100);
    m.gap(Set.of());
    m.book(book(6100), 6100);
    m.book(book(31100), 31100);
    assertThat(m.snapshot(31100).get("markoutSamples")).isEqualTo(Map.of(1000, 1));
    assertThat(m.snapshot(31100).get("missingMarkoutsByReason"))
        .isEqualTo(Map.of("DATA_GAP", Map.of(5000, 1, 30000, 1)));
    assertThat(m.snapshot(31100).get("pendingMarkouts")).isEqualTo(0);
  }

  @Test
  void staleSilenceBeforeFreshReplacementInvalidatesUnobservedHorizons() {
    var m = new PaperMetrics();
    m.book(book(1000), 1000);
    fill(m, "a", "u");
    m.advance(2000, 1000); // Exact freshness boundary is valid.
    m.book(book(2000), 2000);
    m.advance(3001, 1000);
    m.book(book(6000), 6000);
    assertThat(m.snapshot(6000).get("markoutSamples")).isEqualTo(Map.of(1000, 1));
    assertThat(m.snapshot(6000).get("missingMarkoutsByReason"))
        .isEqualTo(Map.of("STALE_DEPTH", Map.of(5000, 1, 30000, 1)));
  }

  @Test
  void invalidSnapshotCannotBeRepairedForAnEarlierFill() {
    for (String corruption : List.of("future", "regression", "empty", "crossed")) {
      var m = new PaperMetrics();
      m.book(book(1000), 1000);
      fill(m, "a", "u");
      var bad = (com.fasterxml.jackson.databind.node.ObjectNode) book(1500);
      switch (corruption) {
        case "future" -> bad.put("sourceMs", 1501);
        case "regression" -> bad.put("sourceMs", 999);
        case "empty" -> bad.putArray("bids");
        case "crossed" -> bad.putArray("bids").addObject().put("price", "0.7");
        default -> throw new AssertionError(corruption);
      }
      m.book(bad, 1500);
      m.book(book(2100), 2100);
      assertThat((Map<?, ?>) m.snapshot(2100).get("markoutSamples")).isEmpty();
      assertThat(m.snapshot(2100).get("missingMarkoutsByReason"))
          .isEqualTo(Map.of("INVALID_BOOK", Map.of(1000, 1, 5000, 1, 30000, 1)));
    }
  }

  @Test
  void staleIncomingBookCannotSupplyAnOtherwiseDueMarkout() {
    var m = new PaperMetrics();
    fill(m, "a", "u");
    m.book(book(2100), 3201, 1000);
    assertThat((Map<?, ?>) m.snapshot(3201).get("markoutSamples")).isEmpty();
    assertThat(m.snapshot(3201).get("missingMarkoutsByReason"))
        .isEqualTo(Map.of("STALE_DEPTH", Map.of(1000, 1, 5000, 1, 30000, 1)));
  }

  @Test
  void expiredObservationsAreMissingNotZeroPnlAndSnapshotIsDetached() {
    var m = new PaperMetrics();
    fill(m, "a", "u");
    var before = m.snapshot(4001);
    assertThat(before.get("missingMarkoutsByReason"))
        .isEqualTo(Map.of("OBSERVATION_WINDOW_EXPIRED", Map.of(1000, 1)));
    m.gap(Set.of());
    assertThat((Map<?, ?>) m.snapshot(4001).get("markoutPnl")).isEmpty();
    assertThat(before.get("missingMarkoutsByReason"))
        .isEqualTo(Map.of("OBSERVATION_WINDOW_EXPIRED", Map.of(1000, 1)));
    assertThat(m.snapshot(4001).get("pendingMarkouts")).isEqualTo(0);
  }
}
