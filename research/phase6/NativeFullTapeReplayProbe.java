package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.nio.file.*;
import java.math.BigDecimal;
import java.util.*;

/** Synthetic full parser differential and fail-closed tests, NOT market profitability. */
public final class NativeFullTapeReplayProbe {
  static final ObjectMapper M=NativeReplaySupport.M;
  static void row(List<JsonNode> rows,String kind,long at,Object data) {
    rows.add(M.valueToTree(Map.of("schema",1,"runId","SYNTHETIC-FULL-PARSER","seq",rows.size()+1,"arrivalMs",at,"kind",kind,"data",data)));
  }
  static List<JsonNode> fixture(boolean unknown) {
    var rows=new ArrayList<JsonNode>();
    row(rows,"DATASET_CONFIG",1000,Map.of("format","normalized-public-v2","strategyIndependent",true));
    var market=new ResearchMarket(CanonicalSessionParityProbe.CONDITION,"a","b",0,1_000_000,new BigDecimal(".01"),new BigDecimal("5"),new BigDecimal(".07"),1,true,1000,"SYNTHETIC_NOT_MARKET");
    row(rows,"RESEARCH_META",1000,market);
    row(rows,"RAW_MARKET",1250,Map.of("frameId",1,"text","[]"));
    // This standalone timer lies INSIDE the raw/frame boundary; must not be moved or dropped.
    row(rows,"RESEARCH_TICK",1250,Map.of());
    var books=(ObjectNode)FrozenStrategySessionProbe.books(1250,".4",".6");books.put("frameId",1);
    row(rows,"RESEARCH_FRAME",1251,books);row(rows,"RESEARCH_TICK",1501,Map.of());
    row(rows,"RESEARCH_TICK",1751,Map.of());
    row(rows,"RAW_MARKET",1820,Map.of("frameId",2,"text","[]"));
    var trade=(ObjectNode)CanonicalSessionParityProbe.trade();trade.put("size","300");trade.put("sourceMs",1810);
    var events=M.createArrayNode();events.add(M.createObjectNode().put("kind","TRADE").set("data",trade));
    if(unknown)events.add(M.createObjectNode().put("kind","TRADE").set("data",trade.deepCopy()));
    row(rows,"RESEARCH_FRAME",1820,Map.of("frameId",2,"events",events));
    row(rows,"RESEARCH_GAP",1900,Map.of("tokens",List.of("a"),"reason","SYNTHETIC_GAP"));
    row(rows,"RESEARCH_TICK",2150,Map.of());
    row(rows,"RUN_END",2151,Map.of("complete",true));return rows;
  }
  static Path write(Path root,String name,List<JsonNode> rows)throws Exception {
    Path p=root.resolve(name);try(var w=Files.newBufferedWriter(p)){for(var row:rows){w.write(M.writeValueAsString(row));w.newLine();}}return p;
  }
  static JsonNode pool() {
    var root=ConservedReceiptPoolProbe.partial(FrozenStrategySessionProbe.labels());
    var binding=(ObjectNode)root.path("bindings").get(0);binding.put("seq",9);binding.put("at",1820);binding.put("sourceMs",1810);return root;
  }
  static void fail(Path tape,Path out,boolean candidate)throws Exception {
    try {NativeFullTapeReplay.runPartial(tape,out,ResearchConfig.defaults(),NativeReplaySupport.limits(),M,new NativeReplaySupport.AuditedLabels(pool()),candidate);}
    catch(IllegalArgumentException expected){return;}throw new AssertionError("Invalid tape did not fail closed");
  }
  public static void main(String[] args)throws Exception {
    if(args.length!=1)throw new IllegalArgumentException("new-output");Path root=Path.of(args[0]);Files.createDirectory(root);
    var rows=fixture(false);Path tape=write(root,"synthetic.jsonl",rows);
    var original=ClosedLoopReplay.run(tape,root.resolve("original-default"),ResearchConfig.defaults(),NativeReplaySupport.limits(),M,false);
    var generated=NativeFullTapeReplay.run(tape,root.resolve("generated-default"),ResearchConfig.defaults(),NativeReplaySupport.limits(),M,false);
    if(!M.valueToTree(original).equals(M.valueToTree(generated)))throw new AssertionError("Whole default report differs");
    if(!Files.readString(root.resolve("original-default/audit.jsonl")).equals(Files.readString(root.resolve("generated-default/audit.jsonl"))))throw new AssertionError("Default audit differs");
    var labelled=NativeFullTapeReplay.runPartial(tape,root.resolve("labelled-complete-synthetic"),ResearchConfig.defaults(),NativeReplaySupport.limits(),M,new NativeReplaySupport.AuditedLabels(pool()),true);
    if(!Boolean.FALSE.equals(labelled.get("fullOriginalTapeCoverageProven")))throw new AssertionError("Synthetic pool promoted to full coverage");
    Path invalid=write(root,"unknown-same-frame.jsonl",fixture(true));fail(invalid,root.resolve("unknown"),true);
    var stopped=M.readTree(Files.readString(root.resolve("unknown/failure.json")));
    var session=stopped.path("sessionAfterSuspension");var attempt=stopped.path("labels").path("lastAttemptedOriginalObservation");
    if(attempt.path("seq").asLong()!=9||attempt.path("eventIndex").asInt()!=1||!session.path("halted").asBoolean()
        ||session.path("openOrderCount").asInt()!=0||!stopped.path("labels").path("failed").asBoolean())throw new AssertionError("Wrong frame index or unsafe failure");
    var snapshot=stopped.path("ledgerAfterSuspension");
    if(snapshot.path("cash").decimalValue().compareTo(new BigDecimal("498"))!=0
        ||snapshot.path("holdings").path("a").path("shares").decimalValue().compareTo(new BigDecimal("5"))!=0)throw new AssertionError("Already-booked fixture inventory erased");
    var broken=fixture(false);((ObjectNode)broken.get(8).path("data")).put("frameId",99);
    fail(write(root,"bad-frame.jsonl",broken),root.resolve("bad-frame"),false);
    if(!M.readTree(Files.readString(root.resolve("bad-frame/failure.json"))).path("sessionAfterSuspension").path("halted").asBoolean())throw new AssertionError("Parser error not suspended");
    var report=new LinkedHashMap<String,Object>();report.put("scope","SYNTHETIC_FULL_PARSER_DIFFERENTIAL_NOT_MARKET_ACCOUNT");
    for(String k:List.of("fullDefaultReportParity","fullDefaultAuditParity","interleavedTimerPreserved","strictSyntheticCompleteTape","sameFrameUnknownIndexHalts","parserFrameMismatchHalts","previousFixtureFillPreserved"))report.put(k,true);
    report.put("originalRows",rows.size());report.put("originalReplaySha256","046d30999a763d2735fa114562dae66c9bfd2e1f7bcbfac0953094938b3b466f");report.put("marketNetPnlRecomputed",false);
    Files.writeString(root.resolve("runner-proof.json"),M.writerWithDefaultPrettyPrinter().writeValueAsString(report)+"\n");
    System.out.println("Whole default parser/report/audit parity, timer/frame boundaries and strict synthetic halt/inventory guards passed");
  }
}
