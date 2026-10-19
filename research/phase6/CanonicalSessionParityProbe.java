package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.risk.AccountLedger;
import java.math.BigDecimal;
import java.nio.file.*;
import java.time.*;
import java.util.*;

/** Synthetic DEFAULT-path parity oracle, compiled against BOTH untouched and research-built cores. */
public final class CanonicalSessionParityProbe {
  static final ObjectMapper M=new ObjectMapper().findAndRegisterModules();
  static final String CONDITION="0x"+"a".repeat(64);
  static JsonNode node(Object o){return M.valueToTree(o);}
  static AccountLedger account(Path root) {
    return new AccountLedger(root.resolve("ledger.json"),M,new BigDecimal("500"),
        new AccountLedger.Limits(new BigDecimal("25"),new BigDecimal("25"),new BigDecimal("250"),new BigDecimal("25"),new BigDecimal("50")),
        Clock.fixed(Instant.parse("2026-10-19T00:00:00Z"),ZoneOffset.UTC));
  }
  static void feed(ResearchSession session,boolean mixed) {
    var market=new ResearchMarket(CONDITION,"a","b",0,1_000_000,new BigDecimal(".01"),new BigDecimal("5"),new BigDecimal(".07"),1,true,1000,"SYNTHETIC_TEST_NOT_MARKET");
    accept(session,mixed,"META",1000,node(market),1);
    var events=new ArrayList<Object>();
    for(String token:List.of("a","b"))events.add(Map.of("kind","BOOK","data",Map.of("token",token,"sourceMs",1250,
        "bids",List.of(Map.of("price",".4","size","100")),"asks",List.of(Map.of("price",".6","size","100")))));
    accept(session,mixed,"FRAME",1251,node(Map.of("events",events)),2);
    accept(session,mixed,"TICK",1501,M.createObjectNode(),3);
    var print=(com.fasterxml.jackson.databind.node.ObjectNode)trade();
    if(!mixed)print.put("price",".41"); // Legacy public-print model requires EXACT order price, not a crossing print.
    accept(session,mixed,"TRADE",1570,print,4);
  }
  static JsonNode trade(){return node(Map.of("token","a","side","SELL","price",".4","size","30","sourceMs",1560,"tradeId",ConservedMixedReplayLabelsProbe.RAW));}
  static void accept(ResearchSession s,boolean mixed,String kind,long at,JsonNode data,long seq){if(mixed)s.acceptReplay(kind,at,data,seq);else s.accept(kind,at,data);}
  public static void main(String[] args)throws Exception {
    if(args.length!=1)throw new IllegalArgumentException("new-out directory required");Path root=Path.of(args[0]);Files.createDirectory(root);
    try(var ledger=account(root);var session=new ResearchSession(ledger,ResearchConfig.defaults(),M,root.resolve("state.json"),(k,v)->{},false,"SYNTHETIC-PARITY")) {
      feed(session,false);
      var report=new TreeMap<String,Object>(session.report());
      if(ledger.snapshot().cash().compareTo(new BigDecimal("497.95"))!=0||ledger.snapshot().holdings().get("a").shares().compareTo(new BigDecimal("5"))!=0)
        throw new AssertionError("Unexpected default canonical synthetic account");
      Files.writeString(root.resolve("parity.json"),M.writerWithDefaultPrettyPrinter().writeValueAsString(node(report))+"\n");
    }
  }
}
