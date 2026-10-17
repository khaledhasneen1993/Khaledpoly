package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.Set;
import org.junit.jupiter.api.Test;

class ClobMarketParametersTest {
  final ObjectMapper mapper = new ObjectMapper();

  ObjectNode fixture() throws Exception {
    return (ObjectNode)
        mapper.readTree(
            "{\"mts\":0.01,\"mos\":5,\"ao\":true,\"fd\":{\"r\":0.07,\"e\":1,\"to\":true},\"t\":[{\"t\":\"1\"},{\"t\":\"2\"}]}");
  }

  @Test
  void actualV2CurveAndMembershipAreRequired() throws Exception {
    var p = ClobMarketParameters.parse(fixture(), "condition", Set.of("1", "2"));
    assertThat(p.fees().rate()).isEqualByComparingTo("0.07");
    assertThat(
            p.fees().fee(new java.math.BigDecimal("100"), new java.math.BigDecimal("0.5"), false))
        .isEqualByComparingTo("1.75");
    assertThat(p.accepting()).isTrue();
    assertThatThrownBy(() -> ClobMarketParameters.parse(fixture(), "condition", Set.of("1", "3")))
        .isInstanceOf(IllegalArgumentException.class);
    var missing = fixture();
    missing.remove("fd");
    assertThatThrownBy(() -> ClobMarketParameters.parse(missing, "condition", Set.of("1", "2")))
        .isInstanceOf(IllegalArgumentException.class);
    missing.put("tbf", 0).put("mbf", 0);
    missing.remove("ao");
    assertThat(ClobMarketParameters.parse(missing, "condition", Set.of("1", "2")).accepting())
        .isFalse();
  }

  @Test
  void refusesUnsupportedOrFractionalFeeSchedules() throws Exception {
    for (String value : new String[] {"-1", "1.5", "9"}) {
      var n = fixture();
      ((ObjectNode) n.path("fd")).put("e", value);
      assertThatThrownBy(() -> ClobMarketParameters.parse(n, "condition", Set.of("1", "2")))
          .isInstanceOf(RuntimeException.class);
    }
    var n = fixture();
    ((ObjectNode) n.path("fd")).put("to", false);
    assertThatThrownBy(() -> ClobMarketParameters.parse(n, "condition", Set.of("1", "2")))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
