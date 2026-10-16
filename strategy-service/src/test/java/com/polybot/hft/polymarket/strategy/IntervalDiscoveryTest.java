package com.polybot.hft.polymarket.strategy;

import static org.assertj.core.api.Assertions.*;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class IntervalDiscoveryTest {
  @Test
  void rollsFiveMinuteWindowsAtExactBoundary() {
    var before =
        GabagoolMarketDiscovery.candidateIntervalSlugs("btc", Instant.ofEpochSecond(1799), 300);
    var after =
        GabagoolMarketDiscovery.candidateIntervalSlugs("btc", Instant.ofEpochSecond(1800), 300);
    assertThat(before)
        .containsExactly("btc-updown-5m-1200", "btc-updown-5m-1500", "btc-updown-5m-1800");
    assertThat(after)
        .containsExactly("btc-updown-5m-1500", "btc-updown-5m-1800", "btc-updown-5m-2100");
  }
}
