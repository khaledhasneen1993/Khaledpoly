package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class RawTapeIsolationTest {
  final ObjectMapper mapper = new ObjectMapper();
  final long base = 1800000000000L;

  String book(String token, long at) {
    return "{\"event_type\":\"book\",\"asset_id\":\""
        + token
        + "\",\"timestamp\":\""
        + at
        + "\",\"bids\":[{\"price\":\"0.4\",\"size\":\"10\"}],\"asks\":[{\"price\":\"0.6\",\"size\":\"10\"}]}";
  }

  String delta(String token, long at) {
    return "{\"event_type\":\"price_change\",\"timestamp\":\""
        + at
        + "\",\"price_changes\":[{\"asset_id\":\""
        + token
        + "\",\"side\":\"BUY\",\"price\":\"0.4\",\"size\":\"9\"}]}";
  }

  @Test
  void olderSourceIsIgnoredWithoutDeletingAnUnrelatedValidBook() throws Exception {
    var decoder = new RawTapeNormalizer(mapper);
    var output = new ArrayList<String>();
    java.util.function.BiConsumer<String, JsonNode> sink =
        (k, n) -> output.add(k + ":" + n.path("token").asText());
    decoder.accept(book("a", base), base, sink);
    decoder.accept(book("b", base), base, sink);
    decoder.accept(book("a", base - 1), base, sink);
    decoder.accept(delta("a", base - 1), base, sink);
    decoder.accept(delta("b", base + 1), base + 1, sink);
    assertThat(output).containsExactly("BOOK:a", "BOOK:b", "BOOK:b");
  }

  @Test
  void missingSnapshotRemainsUntradableAndDoesNotEraseTheOtherMarket() throws Exception {
    var decoder = new RawTapeNormalizer(mapper);
    var output = new ArrayList<String>();
    java.util.function.BiConsumer<String, JsonNode> sink =
        (k, n) -> output.add(k + ":" + n.path("token").asText());
    decoder.accept(book("b", base), base, sink);
    decoder.accept(delta("a", base), base, sink);
    decoder.accept(delta("a", base + 1), base + 1, sink);
    decoder.accept(delta("b", base + 1), base + 1, sink);
    assertThat(output).containsExactly("BOOK:b", "BOOK:b");
    decoder.reset();
    decoder.accept(delta("b", base + 2), base + 2, sink);
    assertThat(output).containsExactly("BOOK:b", "BOOK:b");
    decoder.accept(book("b", base + 3), base + 3, sink);
    assertThat(output.getLast()).isEqualTo("BOOK:b");
  }

  @Test
  void missingDeltaAdvancesSourceWatermarkSoAnOlderSnapshotCannotRestoreTrading() throws Exception {
    var decoder = new RawTapeNormalizer(mapper);
    var output = new ArrayList<String>();
    java.util.function.BiConsumer<String, JsonNode> sink = (k, n) -> output.add(k);
    decoder.accept(delta("a", base + 1), base + 1, sink);
    decoder.accept(book("a", base), base + 1, sink);
    assertThat(output).isEmpty();
    decoder.accept(book("a", base + 1), base + 1, sink);
    assertThat(output).containsExactly("BOOK");
  }

  @Test
  void staleTradeAndSupersededBookPreserveBothCurrentTokens() throws Exception {
    var decoder = new RawTapeNormalizer(mapper);
    var output = new ArrayList<String>();
    java.util.function.BiConsumer<String, JsonNode> sink =
        (k, n) -> output.add(k + ":" + n.path("token").asText());
    decoder.accept(book("a", base), base, sink);
    decoder.accept(book("b", base), base, sink);
    decoder.accept(
        "{\"event_type\":\"last_trade_price\",\"asset_id\":\"a\",\"timestamp\":\""
            + (base - 90000)
            + "\",\"price\":\".4\",\"size\":\"5\",\"side\":\"SELL\"}",
        base,
        sink);
    decoder.accept(delta("a", base + 1), base + 1, sink);
    decoder.accept(book("a", base - 90000), base + 2, sink);
    decoder.accept(delta("a", base + 3), base + 3, sink);
    decoder.accept(delta("b", base + 3), base + 3, sink);
    assertThat(output).containsExactly("BOOK:a", "BOOK:b", "BOOK:a", "BOOK:a", "BOOK:b");
  }
  @Test
  void advancingStaleDeltaInvalidatesItsOwnTokenUntilFullSnapshot() throws Exception {
    var decoder=new RawTapeNormalizer(mapper);
    var output=new ArrayList<String>();var gaps=new ArrayList<JsonNode>();
    java.util.function.BiConsumer<String,JsonNode> sink=(kind,data)->{
      output.add(kind+":"+data.path("token").asText());
      if(kind.equals("GAP"))gaps.add(data);
    };
    decoder.accept(book("a",base),base,sink);
    decoder.accept(book("b",base+3000),base+3000,sink);
    decoder.accept(delta("a",base+1),base+3000,sink);
    decoder.accept(delta("a",base+3001),base+3001,sink);
    decoder.accept(delta("b",base+3001),base+3001,sink);
    assertThat(gaps).hasSize(1);
    assertThat(DataGap.tokens(gaps.getFirst())).containsExactly("a");
    assertThat(output).containsExactly("BOOK:a","BOOK:b","GAP:","BOOK:b");
    decoder.accept(book("a",base+3002),base+3002,sink);
    assertThat(output.getLast()).isEqualTo("BOOK:a");
  }

}
