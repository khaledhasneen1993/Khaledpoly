package com.polybot.hft.polymarket.discovery;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.polymarket.ws.LocalOrderBook;
import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class LocalOrderBookTest {
  @Test
  void deletionRevealsNextLevelAndCrossedBookIsRejected() throws Exception {
    var m = new ObjectMapper();
    var b = new LocalOrderBook();
    b.snapshot(
        m.readTree("[{\"price\":\"0.48\",\"size\":\"10\"},{\"price\":\"0.49\",\"size\":\"2\"}]"),
        m.readTree("[{\"price\":\"0.51\",\"size\":\"20\"}]"));
    b.change("BUY", new BigDecimal("0.49"), BigDecimal.ZERO);
    assertThat(b.best().bid()).isEqualByComparingTo("0.48");
    assertThat(b.best().bidSize()).isEqualByComparingTo("10");
    assertThatThrownBy(() -> b.change("BUY", new BigDecimal("0.52"), BigDecimal.ONE))
        .isInstanceOf(IllegalStateException.class);
  }
}
