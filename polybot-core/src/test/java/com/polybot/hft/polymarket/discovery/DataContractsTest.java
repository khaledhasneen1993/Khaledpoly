package com.polybot.hft.polymarket.discovery;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.polymarket.data.DataApiV2;
import org.junit.jupiter.api.Test;

class DataContractsTest {
  ObjectMapper m = new ObjectMapper();

  @Test
  void prefersV2PositionIds() throws Exception {
    assertThat(
            MarketAssetIds.parse(
                m.readTree(
                    "{\"version\":\"v2\",\"positionIds\":[\"123\",\"456\"],\"clobTokenIds\":\"[7,8]\"}")))
        .containsExactly("123", "456");
    assertThatThrownBy(() -> MarketAssetIds.parse(m.readTree("{}")))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void normalizesAndValidatesCursorEnvelope() throws Exception {
    var page =
        m.readTree(
            "{\"data\":[{\"token_id\":\"123\",\"current_size\":2}],\"pagination\":{\"next_cursor\":null,\"has_more\":false}}");
    assertThat(DataApiV2.rows(page).get(0).path("asset").asText()).isEqualTo("123");
    assertThat(DataApiV2.next(page)).isNull();
    assertThatThrownBy(() -> DataApiV2.rows(m.readTree("[]")))
        .isInstanceOf(IllegalStateException.class);
  }
}
