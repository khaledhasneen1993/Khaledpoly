package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.io.*;
import java.math.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Offline adapter validation only. No account replay, pricing changes, orders or PnL. */
public final class ConservedMixedReplayLabelsProbe {
  static final ObjectMapper M=new ObjectMapper().enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS);
  static final String TX="0x"+"1".repeat(64),EX="0xe111180000d2663c0091e4f400237545b87b996b";
  static final String RAW="{\"transaction_hash\":\""+TX+"\"}";
  static JsonNode node(Object value){return M.valueToTree(value);}
  static ObjectNode fixture(String route,boolean buy) {
    String makerToken=route.equals("DIRECT")?"a":"b",side=buy?"BUY":"SELL",makerSide=route.equals("DIRECT")?(buy?"SELL":"BUY"):side;
    long q=30_000_000,c=12_000_000,takerCost=route.equals("DIRECT")?c:q-c;
    var maker=node(Map.of("token",makerToken,"side",makerSide,"logIndex",2,"makingRaw",makerSide.equals("BUY")?c:q,"takingRaw",makerSide.equals("BUY")?q:c));
    var taker=node(Map.of("token","a","side",side,"makingRaw",buy?takerCost:q,"takingRaw",buy?q:takerCost));
    var binding=node(Map.ofEntries(Map.entry("seq",1),Map.entry("eventIndex",0),Map.entry("at",1270),Map.entry("sourceMs",1260),
        Map.entry("transactionHash",TX),Map.entry("publicTradeIdSha256",ConservedMixedReplayLabels.hash(RAW)),Map.entry("token","a"),Map.entry("side",side),
        Map.entry("price","0.5"),Map.entry("size","30"),Map.entry("pair",List.of("a","b")),
        Map.entry("matches",List.of(Map.of("exchange",EX,"ordersMatchedLogIndex",3,"matchType",route,"maker",maker,"taker",taker)))));
    var root=M.createObjectNode();root.put("schema",1);root.put("experiment","CONSERVED-MIXED-LAB0");
    for(String k:List.of("partialLabels","adapterOnlyNotAccountReplay"))root.put(k,true);
    for(String k:List.of("liveAllowed","independentPaperQualificationAllowed","candidateAccountSimulated","netPnlRecomputed"))root.put(k,false);
    root.put("modelFillsCreated",0);root.put("expectedBindingCount",1);root.put("expectedComponentCount",1);
    for(String k:List.of("logicalTapeSha256","contextLogicalSha256","contextCompressedSha256"))root.put(k,"0".repeat(64));
    root.set("coverage",node(Map.of("pair",List.of("a","b"),"afterMs",1000,"throughMs",2000,"allOriginalPairObservationsWithinWindow",true,"unknownScopedObservation","FAIL_CLOSED")));
    root.set("bindings",node(List.of(binding)));return root;
  }
  static ObjectNode trade(boolean buy){return (ObjectNode)node(Map.of("token","a","side",buy?"BUY":"SELL","price","0.5","size","30","sourceMs",1260,"tradeId",RAW));}
  static void reject(Runnable action){try{action.run();}catch(IllegalArgumentException|IllegalStateException expected){return;}throw new AssertionError("Invalid manifest/observation accepted");}

  static void selfTest() {
    int routes=0,negatives=0;
    for(String route:List.of("DIRECT","MINT","MERGE"))for(boolean buy:List.of(true,false)) {
      if(!route.equals("DIRECT")&&!route.equals(buy?"MINT":"MERGE"))continue;
      var root=fixture(route,buy);var labels=new ConservedMixedReplayLabels(root,M);var b=labels.resolve(1,0,1270,trade(buy));
      var p=b.portions().get(0);boolean makerBuy=p.buy();String token=p.token();
      var engine=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));
      for(String t:List.of("a","b"))engine.accept("BOOK",900,node(Map.of("token",t,"sourceMs",900,
          "bids",List.of(Map.of("price",makerBuy?".4":".3","size","10")),"asks",List.of(Map.of("price",makerBuy?".7":".4","size","10")))));
      engine.accept("ORDER",1000,node(Map.of("id","fixture","token",token,"side",makerBuy?"BUY":"SELL","price",".4","size","5")));
      engine.accept("TICK",1251,M.createObjectNode());
      var update=engine.acceptSettlement(1270,trade(buy),b);
      if(update.fills().size()!=1||update.fills().get(0).size().compareTo(new BigDecimal("5"))!=0)throw new AssertionError("Canonical queue bridge mismatch");
      labels.requireConsumed();routes++;
      reject(()->labels.resolve(1,0,1270,trade(buy)));negatives++;
      var duplicate=labels.resolve(2,0,1270,trade(buy));if(!duplicate.portions().isEmpty()||!duplicate.pair().isEmpty())throw new AssertionError("Covered aggregate doubled");
      var unknown=trade(buy);unknown.put("tradeId","{\"transaction_hash\":\"0x"+"2".repeat(64)+"\"}");
      reject(()->labels.resolve(3,0,1270,unknown));negatives++;
    }
    for(String field:List.of("liveAllowed","independentPaperQualificationAllowed","candidateAccountSimulated","netPnlRecomputed")) {
      var bad=fixture("MINT",true);bad.put(field,true);reject(()->new ConservedMixedReplayLabels(bad,M));negatives++;
    }
    for(String field:List.of("makingRaw","takingRaw")) {
      var bad=fixture("MINT",true);((ObjectNode)bad.path("bindings").get(0).path("matches").get(0).path("taker")).put(field,999);
      reject(()->new ConservedMixedReplayLabels(bad,M));negatives++;
    }
    var fractional=fixture("MINT",true);((ObjectNode)fractional.path("bindings").get(0).path("matches").get(0).path("maker")).put("makingRaw",1.5);
    reject(()->new ConservedMixedReplayLabels(fractional,M));negatives++;
    var dup=fixture("MINT",true);var rows=(ArrayNode)dup.path("bindings").get(0).path("matches");rows.add(rows.get(0).deepCopy());
    reject(()->new ConservedMixedReplayLabels(dup,M));negatives++;
    var wrongRoute=fixture("MERGE",false);((ObjectNode)wrongRoute.path("bindings").get(0).path("matches").get(0)).put("matchType","MINT");
    reject(()->new ConservedMixedReplayLabels(wrongRoute,M));negatives++;
    var incomplete=new ConservedMixedReplayLabels(fixture("MINT",true),M);reject(incomplete::requireConsumed);negatives++;
    for(String field:List.of("price","size","sourceMs","tradeId")) {
      var t=trade(true);if(field.equals("sourceMs"))t.put(field,1261);else t.put(field,field.equals("tradeId")?RAW+" ":"0.6");
      var labels=new ConservedMixedReplayLabels(fixture("MINT",true),M);reject(()->labels.resolve(1,0,1270,t));negatives++;
    }
    for(boolean buy:List.of(true,false)) {
      var rounded=fixture(buy?"MINT":"MERGE",buy);var n=(ObjectNode)rounded.path("bindings").get(0);
      var q=BigInteger.TEN.pow(40);var c=q.divide(BigInteger.TWO).add(buy?BigInteger.ONE:BigInteger.ONE.negate());
      var match=n.path("matches").get(0);var m=(ObjectNode)match.path("maker");var t=(ObjectNode)match.path("taker");
      m.put("makingRaw",buy?c:q);m.put("takingRaw",buy?q:c);t.put("makingRaw",buy?q.subtract(c):q);t.put("takingRaw",buy?q:q.subtract(c));
      n.put("size",new BigDecimal(q,6).toPlainString());
      var b=new ConservedMixedReplayLabels(rounded,M);var trade=trade(buy);trade.put("size",new BigDecimal(q,6).toPlainString());
      int comparison=b.resolve(1,0,1270,trade).portions().get(0).price().compareTo(new BigDecimal(".5"));
      if(buy?comparison<=0:comparison>=0)throw new AssertionError("BUY-UP/SELL-DOWN rounded across half-price boundary");
    }
    System.out.println(routes+" canonical DIRECT/MINT/MERGE queue-bridge cases; "+negatives+" rejection cases; 2 BUY-UP/SELL-DOWN boundary cases passed (synthetic, not market fills)");
  }

  public static void main(String[] args)throws Exception {
    if(args.length==1&&args[0].equals("--self-test")){selfTest();return;}
    if(args.length!=3)throw new IllegalArgumentException("labels.json original.context.jsonl.gz adapter-report.json");
    Path manifest=Path.of(args[0]),context=Path.of(args[1]);
    if(Files.size(manifest)>16_000_000||Files.size(context)>32_000_000)throw new IllegalArgumentException("Bounded adapter inputs required");
    var root=M.readTree(Files.readString(manifest));var adapter=new ConservedMixedReplayLabels(root,M);
    var compressed=MessageDigest.getInstance("SHA-256");try(var in=Files.newInputStream(context)){byte[] buf=new byte[65536];for(int n;(n=in.read(buf))!=-1;)compressed.update(buf,0,n);}
    if(!HexFormat.of().formatHex(compressed.digest()).equals(root.path("contextCompressedSha256").asText()))throw new IllegalArgumentException("Wrong compressed original context");
    var logical=MessageDigest.getInstance("SHA-256");long after=root.path("coverage").path("afterMs").asLong(),through=root.path("coverage").path("throughMs").asLong();
    long previousSeq=-1,previousAt=-1,total=0;int observations=0;var portionsDigest=MessageDigest.getInstance("SHA-256");
    try(var in=new GZIPInputStream(Files.newInputStream(context));var digest=new java.security.DigestInputStream(in,logical);
        var reader=new BufferedReader(new InputStreamReader(digest,java.nio.charset.StandardCharsets.UTF_8))) {
      for(String line;(line=reader.readLine())!=null;) {
        if(line.length()>32_000_000||(total+=line.length())>512_000_000)throw new IllegalArgumentException("Bounded original context exceeded");
        var row=M.readTree(line).path("input");long seq=row.path("seq").asLong(),at=row.path("arrivalMs").asLong();
        if(seq<=previousSeq||at<previousAt)throw new IllegalArgumentException("Changed original chronology");previousSeq=seq;previousAt=at;
        if(at<=after||at>through)continue;
        var events=row.path("kind").asText().equals("RESEARCH_FRAME")?row.path("data").path("events"):node(List.of(Map.of("kind",row.path("kind").asText().substring(9),"data",row.path("data"))));int index=0;
        for(var event:events){if(event.path("kind").asText().equals("TRADE")){var b=adapter.resolve(seq,index,at,event.path("data"));if(b!=null&&!b.portions().isEmpty()) {
          observations++;
          for(var p:b.portions())portionsDigest.update((seq+"|"+index+"|"+p.identity()+"|"+p.token()+"|"+(p.buy()?"BUY":"SELL")+"|"+p.price().toPlainString()+"|"+p.quantity().toPlainString()+"\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }}index++;}
      }
    }
    if(!HexFormat.of().formatHex(logical.digest()).equals(root.path("contextLogicalSha256").asText()))throw new IllegalArgumentException("Wrong original context hash");
    adapter.requireConsumed();var report=new LinkedHashMap<String,Object>(adapter.report());report.put("originalObservations",observations);
    report.put("modelFillsCreated",0);report.put("netPnlRecomputed",false);report.put("newPublicReads",0);
    report.put("labelsSha256",ConservedMixedReplayLabels.hash(Files.readString(manifest)));
    report.put("portionsLogicalSha256",HexFormat.of().formatHex(portionsDigest.digest()));
    Files.writeString(Path.of(args[2]),M.writerWithDefaultPrettyPrinter().writeValueAsString(report)+"\n");
  }
}
