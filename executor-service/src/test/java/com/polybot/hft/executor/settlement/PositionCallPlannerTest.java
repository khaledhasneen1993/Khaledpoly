package com.polybot.hft.executor.settlement;

import static org.assertj.core.api.Assertions.*;

import java.math.BigInteger;
import org.junit.jupiter.api.Test;

class PositionCallPlannerTest {
  @Test
  void routesCtfAndV2ToDifferentContracts() {
    var ctf = PositionCallPlanner.merge("v1", false, "0x" + "11".repeat(32), BigInteger.TEN);
    var v2 = PositionCallPlanner.merge("v2", false, "0x" + "11".repeat(31), BigInteger.TEN);
    assertThat(ctf.target()).isEqualTo("0xAdA100Db00Ca00073811820692005400218FcE1f");
    assertThat(v2.target()).isEqualTo("0x12121212006e4CD160D18e3f00711DA5c3372600");
    assertThat(ctf.data()).startsWith("0x");
    assertThat(v2.data()).isNotEqualTo(ctf.data());
  }

  @Test
  void rejectsMalformedProtocolIdAndOutcome() {
    assertThatThrownBy(() -> PositionCallPlanner.merge("v2", false, "0x11", BigInteger.TEN))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(
            () ->
                PositionCallPlanner.redeem("v2", false, "0x" + "11".repeat(31), 2, BigInteger.TEN))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
