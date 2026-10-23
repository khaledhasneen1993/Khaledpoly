package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class MatchingDiagnosticsTest {
  @Test void explainsQueueAndActivationWithoutCreatingExtraFills() throws Exception {
    var h = new PaperMatchingEngineTest();
    h.book(1000, "10"); h.order("a", "BUY", "0.4");
    assertThat(h.trade(1050, "early", "SELL", "0.4", "100").fills()).isEmpty();
    assertThat(h.trade(1101, "queue", "SELL", "0.4", "19").fills()).isEmpty();
    assertThat(h.trade(1102, "queue", "SELL", "0.4", "19").fills()).isEmpty();
    assertThat(h.trade(1103, "wrong-side", "BUY", "0.4", "500").fills()).isEmpty();
    assertThat(h.trade(1104, "wrong-price", "SELL", "0.39", "500").fills()).isEmpty();
    assertThat(h.trade(1105, "eligible", "SELL", "0.4", "6").fills()).singleElement()
        .satisfies(f -> assertThat(f.size()).isEqualByComparingTo("5"));
    var row = h.engine.diagnostics().getFirst();
    assertThat(row.get("initialQueueAhead").toString()).isEqualTo("20");
    assertThat(row.get("eligiblePrintVolume").toString()).isEqualTo("25");
    assertThat(row).containsEntry("terminalReason", "PRINT_FILLED").containsEntry("activeMs", 4L);
    assertThat((Map<String, Long>)row.get("printObservations"))
        .containsEntry("ORDER_NOT_ACTIVE", 1L).containsEntry("QUEUE_NOT_EXHAUSTED", 1L)
        .containsEntry("DUPLICATE_PRINT", 1L).containsEntry("WRONG_AGGRESSOR", 1L)
        .containsEntry("DIFFERENT_PRICE", 1L).containsEntry("ELIGIBLE_PRINT", 2L);
  }

  @Test void reportsCausalPrintRejectionAndTerminalBeforeActivation() throws Exception {
    var h = new PaperMatchingEngineTest();
    h.book(1000, "10"); h.order("a", "BUY", "0.4");
    h.book(1101, "10");
    var stale = h.n("{\"token\":\"u\",\"tradeId\":\"old\",\"side\":\"SELL\",\"price\":\"0.4\",\"size\":\"999\",\"sourceMs\":1100}");
    assertThat(h.engine.accept("TRADE", 1102, stale).fills()).isEmpty();
    h.engine.accept("GAP", 1103, h.n("{\"token\":\"u\",\"reason\":\"test\"}"));
    var row = h.engine.diagnostics().getFirst();
    assertThat((Map<String,Long>)row.get("printObservations")).containsEntry("PRINT_BEFORE_CURRENT_BOOK", 1L);
    assertThat(row).containsEntry("terminalReason", "DATA_GAP:test").containsEntry("terminalMs", 1103L);
    var second = new PaperMatchingEngineTest(); second.book(1000,"10"); second.order("b","BUY","0.4");
    second.engine.accept("GAP",1050,second.n("{}"));
    assertThat(second.engine.diagnostics().getFirst()).containsEntry("activatedMs",null).containsEntry("activeMs",0L);
  }
}
