package com.polybot.hft.polymarket.strategy.service;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.config.HftProperties;
import com.polybot.hft.events.HftEventPublisher;
import com.polybot.hft.polymarket.api.OrderSubmissionResult;
import com.polybot.hft.polymarket.strategy.model.*;
import com.polybot.hft.strategy.executor.ExecutorApiClient;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.time.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class OrderManagerTest {
  @TempDir Path dir;
  ExecutorApiClient api = mock(ExecutorApiClient.class);
  HftEventPublisher events = mock(HftEventPublisher.class);
  ObjectMapper mapper = new ObjectMapper();

  @BeforeEach
  void state() {
    System.setProperty("polybot.orderState", dir.resolve("orders.json").toString());
  }

  @AfterEach
  void cleanup() {
    System.clearProperty("polybot.orderState");
  }

  OrderManager open() {
    return new OrderManager(api, events, Clock.systemUTC(), "test");
  }

  void place(OrderManager manager) {
    when(api.placeLimitOrder(any()))
        .thenReturn(
            new OrderSubmissionResult(
                HftProperties.TradingMode.PAPER,
                null,
                mapper.createObjectNode().put("orderID", "order-1")));
    manager.placeOrder(
        new GabagoolMarket("market", "up", "down", Instant.now().plusSeconds(300), "updown-15m"),
        "up",
        Direction.UP,
        new BigDecimal("0.5"),
        BigDecimal.TEN,
        300,
        new BigDecimal("0.01"),
        null,
        null,
        null,
        OrderManager.PlaceReason.QUOTE);
  }

  @Test
  void failedCancellationRetainsOwnershipAcrossRestart() {
    var manager = open();
    place(manager);
    doThrow(new RuntimeException("timeout")).when(api).cancelOrder("order-1");
    manager.cancelOrder("up", OrderManager.CancelReason.SHUTDOWN, null, null, null);
    assertThat(manager.hasOrder("up")).isTrue();
    manager.close();
    var restored = open();
    assertThat(restored.getOrder("up").orderId()).isEqualTo("order-1");
    restored.close();
  }

  @Test
  void partialFillRetainsRemainingOrder() {
    var manager = open();
    place(manager);
    when(api.getOrder("order-1"))
        .thenReturn(
            mapper
                .createObjectNode()
                .put("status", "PARTIALLY_FILLED")
                .put("matched_size", "2.5")
                .put("remaining_size", "7.5"));
    manager.checkPendingOrders((order, delta) -> assertThat(delta).isEqualByComparingTo("2.5"));
    assertThat(manager.hasOrder("up")).isTrue();
    manager.close();
  }

  @Test
  void submissionTimeoutKeepsDurableIntentAndPreventsDuplicate() {
    when(api.placeLimitOrder(any())).thenThrow(new RuntimeException("timeout"));
    var manager = open();
    var market =
        new GabagoolMarket("market", "up", "down", Instant.now().plusSeconds(300), "updown-15m");
    for (int i = 0; i < 2; i++)
      manager.placeOrder(
          market,
          "up",
          Direction.UP,
          new BigDecimal("0.5"),
          BigDecimal.TEN,
          300,
          null,
          null,
          null,
          null,
          OrderManager.PlaceReason.QUOTE);
    verify(api, times(1)).placeLimitOrder(any());
    assertThat(manager.hasOrder("up")).isTrue();
    manager.close();
  }

  @Test
  void cancelsOrphanPaperOrderBeforeResuming() {
    var manager = open();
    when(api.getOpenOrders())
        .thenReturn(
            mapper
                .createObjectNode()
                .set(
                    "data",
                    mapper
                        .createArrayNode()
                        .add(mapper.createObjectNode().put("id", "sim-orphan"))));
    when(api.getOrder("sim-orphan"))
        .thenReturn(mapper.createObjectNode().put("status", "CANCELED"));
    manager.reconcileOpenOrders();
    verify(api).cancelOrder("sim-orphan");
    manager.close();
  }
}
