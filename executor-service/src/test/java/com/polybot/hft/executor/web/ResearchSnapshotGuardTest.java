package com.polybot.hft.executor.web;

import static org.assertj.core.api.Assertions.*;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class ResearchSnapshotGuardTest {
  @Test
  void refusesMissingOrWeakToken() {
    var controller = new ResearchSnapshotController(null);
    for (String token : new String[] {"", "short", " ".repeat(32)}) {
      ReflectionTestUtils.setField(controller, "token", token);
      assertThatThrownBy(controller::validate).isInstanceOf(IllegalStateException.class);
    }
    ReflectionTestUtils.setField(controller, "token", "phase3-test-token-with-32-characters");
    assertThatCode(controller::validate).doesNotThrowAnyException();
  }
}
