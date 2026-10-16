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

  @org.junit.jupiter.api.Test
  void venueBatchValidatesFinalStateAndRollsBackInvalidBatches() throws Exception {
    var mapper = new com.fasterxml.jackson.databind.ObjectMapper();
    var book = new com.polybot.hft.polymarket.ws.LocalOrderBook();
    book.snapshot(
        mapper.readTree("[{\"price\":\"0.4\",\"size\":\"10\"}]"),
        mapper.readTree("[{\"price\":\"0.5\",\"size\":\"10\"}]"));
    book.changes(
        mapper.readTree(
            "[{\"side\":\"BUY\",\"price\":\"0.6\",\"size\":\"10\"},{\"side\":\"SELL\",\"price\":\"0.5\",\"size\":\"0\"},{\"side\":\"SELL\",\"price\":\"0.7\",\"size\":\"10\"}]"));
    org.assertj.core.api.Assertions.assertThat(book.best().bid()).isEqualByComparingTo("0.6");
    org.assertj.core.api.Assertions.assertThatThrownBy(
            () ->
                book.changes(
                    mapper.readTree("[{\"side\":\"SELL\",\"price\":\"0.3\",\"size\":\"10\"}]")))
        .isInstanceOf(IllegalStateException.class);
    org.assertj.core.api.Assertions.assertThat(book.best().ask()).isEqualByComparingTo("0.7");
  }
}
