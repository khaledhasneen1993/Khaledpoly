package com.polybot.hft.polymarket.discovery;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.domain.OrderSide;
import com.polybot.hft.polymarket.api.LimitOrderRequest;
import com.polybot.hft.polymarket.model.*;
import java.math.BigDecimal;
import java.time.*;
import org.junit.jupiter.api.Test;

class MarketConstraintsTest {
  ObjectMapper m = new ObjectMapper();

  @Test
  void validatesMarketIdentitySizeTickAndExpiry() throws Exception {
    String id = "0x" + "11".repeat(32);
    var book =
        m.readTree(
            "{\"market\":\""
                + id
                + "\",\"asset_id\":\"123\",\"tick_size\":\"0.01\",\"min_order_size\":\"5\"}");
    var market =
        m.readTree(
            "{\"conditionId\":\""
                + id
                + "\",\"version\":\"v2\",\"positionIds\":[\"123\",\"456\"],\"active\":true,\"closed\":false,\"acceptingOrders\":true,\"endDate\":\"2026-10-17T00:00:00Z\"}");
    var policy = MarketConstraints.parse(book, market, m.createObjectNode());
    Clock before = Clock.fixed(Instant.parse("2026-10-16T00:00:00Z"), ZoneOffset.UTC);
    var good =
        new LimitOrderRequest(
            "123",
            OrderSide.BUY,
            new BigDecimal("0.5"),
            BigDecimal.TEN,
            ClobOrderType.GTC,
            null,
            null,
            null,
            null,
            null,
            null,
            null);
    policy.validate(good, before);
    assertThatThrownBy(
            () ->
                policy.validate(
                    good, Clock.fixed(Instant.parse("2026-10-18T00:00:00Z"), ZoneOffset.UTC)))
        .isInstanceOf(IllegalStateException.class);
    ((com.fasterxml.jackson.databind.node.ObjectNode) market).put("acceptingOrders", false);
    assertThatThrownBy(() -> MarketConstraints.parse(book, market, m.createObjectNode()))
        .isInstanceOf(IllegalStateException.class);
  }
}
