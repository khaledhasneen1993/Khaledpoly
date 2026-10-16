package com.polybot.hft.executor.order;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;

class UserChannelServiceTest {
  @Test
  void routesTradeToBothOrderOwnersWithoutTrustingFillAmount() throws Exception {
    var ids = new java.util.concurrent.ConcurrentHashMap<String, Boolean>();
    var latch = new CountDownLatch(2);
    var service =
        new UserChannelService(
            null,
            null,
            null,
            null,
            new ObjectMapper(),
            Clock.systemUTC(),
            event -> {
              if (event instanceof UserChannelService.OrderChanged update) {
                ids.put(update.orderId(), true);
                latch.countDown();
              }
            });
    try {
      service.receive(
          "{\"event_type\":\"trade\",\"taker_order_id\":\"a\",\"maker_orders\":[{\"order_id\":\"b\"}]}");
      assertThat(latch.await(2, TimeUnit.SECONDS)).isTrue();
      assertThat(ids.keySet()).containsExactlyInAnyOrder("a", "b");
    } finally {
      service.stop();
    }
  }
}
