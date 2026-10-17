package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;
import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.nio.file.Path;
import java.util.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;

class OrderLifecycleRegressionTest {
  @TempDir Path dir;
  final ResearchSessionTest helper = new ResearchSessionTest();
  final ObjectMapper mapper = helper.mapper;

  @Test void validRestingPairSurvivesUnprofitableReplacementQuote() {
    helper.dir=dir;
    try (var ledger=new AccountLedger(dir.resolve("ledger.json"),mapper,helper.b("500"),helper.limits,helper.clock);
        var session=helper.open(ledger)) {
      helper.input(session,"META",0,mapper.valueToTree(helper.market()));
      helper.books(session,0,"0.4","0.45","0.55","0.6");
      helper.tick(session,250);
      assertThat(ledger.snapshot().orders()).hasSize(2);
      // Existing pair costs .97; replacement pair would cost .99 and fail net edge.
      helper.input(session,"BOOK",300,helper.book("a",helper.base+300,"0.42","0.45","100"));
      helper.tick(session,501); helper.tick(session,751);
      assertThat(ledger.snapshot().orders().values()).allSatisfy(o -> assertThat(o.remaining()).isEqualByComparingTo("5"));
      assertThat(session.report().get("openOrderCount")).isEqualTo(2);
    }
  }

  @Test void currentNewEntrySizeDoesNotCancelExistingReservedSize() {
    helper.dir=dir;
    try (var ledger=new AccountLedger(dir.resolve("ledger.json"),mapper,helper.b("500"),helper.limits,helper.clock);
        var session=helper.open(ledger)) {
      var meta=mapper.valueToTree(helper.market());
      ((com.fasterxml.jackson.databind.node.ObjectNode)meta).put("minSize","5");
      helper.input(session,"META",0,meta);
      helper.books(session,0,"0.4","0.6","0.4","0.6");
      helper.tick(session,250);helper.tick(session,501);
      helper.input(session,"BOOK",600,helper.book("a",helper.base+600,"0.4","0.6","40"));
      helper.tick(session,751);helper.tick(session,1002);
      assertThat(session.report().get("openOrderCount")).isEqualTo(2);
    }
  }

  @Test void crossingRestingQuoteStillCancelsWithoutMinimumLifetimeOverride() {
    helper.dir=dir;
    var events=new ArrayList<JsonNode>();
    try (var ledger=new AccountLedger(dir.resolve("ledger.json"),mapper,helper.b("500"),helper.limits,helper.clock);
        var session=new ResearchSession(ledger,ResearchConfig.defaults(),mapper,dir.resolve("s.json"),
            (kind,data)->{if(kind.equals("CANCEL_REQUEST"))events.add(mapper.valueToTree(data));})) {
      helper.enter(session);
      helper.input(session,"BOOK",550,helper.book("a",helper.base+550,"0.3","0.4","100"));
      helper.tick(session,751);
      assertThat(events).isNotEmpty();
      assertThat(events.getFirst().path("reason").asText()).isEqualTo("RESTING_PRICE_INVALID");
    }
  }

  @Test void rejectedLegRequestsPeerCancelImmediatelyButHonorsCancelRace() {
    helper.dir=dir;
    var requests=new ArrayList<JsonNode>();var terminals=new ArrayList<JsonNode>();
    try (var ledger=new AccountLedger(dir.resolve("ledger.json"),mapper,helper.b("500"),helper.limits,helper.clock);
        var session=new ResearchSession(ledger,ResearchConfig.defaults(),mapper,dir.resolve("s.json"),
            (kind,data)->{if(kind.equals("CANCEL_REQUEST"))requests.add(mapper.valueToTree(data));if(kind.equals("ORDER_TERMINAL"))terminals.add(mapper.valueToTree(data));})) {
      helper.input(session,"META",0,mapper.valueToTree(helper.market()));
      helper.books(session,0,"0.4","0.6","0.4","0.6");helper.tick(session,250);
      helper.input(session,"BOOK",490,helper.book("a",helper.base+490,"0.3","0.4","100"));
      helper.tick(session,501);
      assertThat(requests).hasSize(1);
      assertThat(requests.getFirst().path("at").asLong()).isEqualTo(helper.base+501);
      assertThat(requests.getFirst().path("reason").asText()).startsWith("PEER_REJECTED:");
      assertThat(terminals.getFirst().path("reason").asText()).isEqualTo("POST_ONLY_WOULD_CROSS");
      assertThat(session.report().get("openOrderCount")).isEqualTo(1);
      helper.tick(session,750);assertThat(session.report().get("openOrderCount")).isEqualTo(1);
      helper.tick(session,751);assertThat(ledger.snapshot().orders().get(requests.getFirst().path("id").asText()).remaining()).isEqualByComparingTo("0");
    }
  }

  @Test void knownTokenGapCancelsBothLegsButPreservesOtherMarket() {
    helper.dir=dir;
    try (var ledger=new AccountLedger(dir.resolve("ledger.json"),mapper,helper.b("500"),helper.limits,helper.clock);
        var session=helper.open(ledger)) {
      helper.enter(session);
      var second=(com.fasterxml.jackson.databind.node.ObjectNode)mapper.valueToTree(helper.market());
      second.put("condition","0x"+"2".repeat(64));second.put("first","c");second.put("second","d");
      helper.input(session,"META",600,second);
      helper.input(session,"BOOK",600,helper.book("c",helper.base+600,"0.4","0.6","100"));
      helper.input(session,"BOOK",600,helper.book("d",helper.base+600,"0.4","0.6","100"));
      helper.tick(session,751);
      assertThat(session.report().get("openOrderCount")).isEqualTo(4);
      helper.input(session,"GAP",800,mapper.valueToTree(Map.of("reason","invalid_depth","token","a")));
      assertThat(session.report().get("openOrderCount")).isEqualTo(2);
      assertThat(ledger.snapshot().orders().values().stream().filter(o->o.remaining().signum()>0).map(AccountLedger.Reservation::token)).containsExactlyInAnyOrder("c","d");
      helper.input(session,"GAP",850,mapper.valueToTree(Map.of("reason","disconnect")));
      assertThat(session.report().get("openOrderCount")).isEqualTo(0);
    }
  }
}
