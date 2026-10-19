package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Isolated single-order optimistic necessary gate. Never strategy/account/PnL. */
public final class Qw0CausalProbe {
  static final ObjectMapper M=new ObjectMapper().enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS);
  static final JsonNode EMPTY=M.createObjectNode();
  static JsonNode node(Object o){return M.valueToTree(o);}
  static BigDecimal dec(JsonNode n){return new BigDecimal(n.asText());}
  static void noFill(PaperMatchingEngine.Update u){if(!u.fills().isEmpty())throw new AssertionError("No aggregate allocations allowed");}
  static SettlementReplayLabels.Binding binding(JsonNode b,JsonNode trade,long seq,int ix,long at,Set<String> pair) throws Exception {
    if(b.path("seq").asLong()!=seq||b.path("eventIndex").asInt()!=ix||b.path("at").asLong()!=at
        ||b.path("sourceMs").asLong()!=trade.path("sourceMs").asLong()
        ||!M.readTree(trade.path("tradeId").asText()).equals(b.path("sample")))
      throw new IllegalArgumentException("Actual original observation binding differs");
    var sample=b.path("sample");
    if(!sample.path("asset_id").asText().equals(trade.path("token").asText())
        ||!sample.path("side").asText().equals(trade.path("side").asText())
        ||dec(sample.path("price")).compareTo(dec(trade.path("price")))!=0
        ||dec(sample.path("size")).compareTo(dec(trade.path("size")))!=0)
      throw new IllegalArgumentException("Original trade fields differ");
    var portions=new ArrayList<SettlementReplayLabels.Portion>();var seen=new HashSet<String>();
    for(var p:b.path("parts")) {
      if(!p.path("sharesRaw").isIntegralNumber()||!p.path("collateralRaw").isIntegralNumber())throw new IllegalArgumentException("Raw integers required");
      var shares=p.path("sharesRaw").bigIntegerValue();var cost=p.path("collateralRaw").bigIntegerValue();
      String identity=p.path("identity").asText(),token=p.path("token").asText();
      if(shares.signum()<=0||cost.signum()<=0||cost.compareTo(shares)>=0||!pair.contains(token)||!seen.add(identity))
        throw new IllegalArgumentException("Invalid conserved actual portion");
      // Round UP, not to nearest: a BUY must never be credited across a rounded cent boundary.
      portions.add(new SettlementReplayLabels.Portion(identity,token,p.path("buy").asBoolean(),
          new BigDecimal(cost).divide(new BigDecimal(shares),28,RoundingMode.UP),new BigDecimal(shares,6)));
    }
    String hash=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(trade.path("tradeId").asText().getBytes(StandardCharsets.UTF_8)));
    return new SettlementReplayLabels.Binding(seq,ix,at,trade.path("sourceMs").asLong(),hash,
        trade.path("token").asText(),trade.path("side").asText(),dec(trade.path("price")),dec(trade.path("size")),pair,List.copyOf(portions));
  }
  static void selfTest() {
    for(boolean stale:List.of(false,true)) {
      var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));
      for(String t:List.of("a","b"))e.accept("BOOK",900,node(Map.of("token",t,"sourceMs",900,
          "bids",List.of(Map.of("price",".48","size","10")),"asks",List.of(Map.of("price",".6","size","10")))));
      e.accept("ORDER",1000,node(Map.of("id","test","token","a","side","BUY","price",".48","size","5")));
      e.accept("TICK",1251,EMPTY);
      if(stale)e.accept("BOOK",1301,node(Map.of("token","a","sourceMs",1300,
          "bids",List.of(Map.of("price",".48","size","10")),"asks",List.of(Map.of("price",".6","size","10")))));
      long source=stale?1290:1260,at=stale?1310:1270;
      var p=new SettlementReplayLabels.Portion("synthetic-fixture","a",true,new BigDecimal(".48"),new BigDecimal("30"));
      var b=new SettlementReplayLabels.Binding(1,0,at,source,"","b","BUY",new BigDecimal(".52"),new BigDecimal("30"),Set.of("a","b"),List.of(p));
      var u=e.acceptSettlement(at,node(Map.of("sourceMs",source)),b);
      var quantity=u.fills().stream().map(PaperMatchingEngine.Fill::size).reduce(BigDecimal.ZERO,BigDecimal::add);
      if(quantity.compareTo(stale?BigDecimal.ZERO:new BigDecimal("5"))!=0)throw new AssertionError("Actual queue/current-book-source gate differs");
    }
    System.out.println("2 actual-matcher synthetic queue and current-book-source assertions passed");
  }
  public static void main(String[] args)throws Exception {
    if(args.length==1&&args[0].equals("--self-test")){selfTest();return;}
    if(args.length!=3)throw new IllegalArgumentException("context.gz bindings.json report.json");
    JsonNode context;try(var in=new GZIPInputStream(Files.newInputStream(Path.of(args[0])))){context=M.readTree(in);}
    var manifest=M.readTree(Files.readString(Path.of(args[1])));var s=manifest.path("state");
    if(!s.equals(context.path("spec").path("states").get(0))||s.path("originalSequence").asLong()!=243583)
      throw new IllegalArgumentException("Wrong frozen QW0 state");
    var pair=new HashSet<String>();manifest.path("pair").forEach(t->pair.add(t.asText()));
    var labels=new HashMap<String,JsonNode>();var txs=new HashSet<String>();
    for(var b:manifest.path("bindings")) {
      if(labels.putIfAbsent(b.path("seq").asLong()+":"+b.path("eventIndex").asInt(),b)!=null||!txs.add(b.path("transactionHash").asText()))
        throw new IllegalArgumentException("Duplicate original binding");
    }
    if(labels.size()!=39||pair.size()!=2)throw new IllegalArgumentException("Require complete39 target-leg observations");
    var seen=new HashSet<String>();var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));
    var conditional=new ArrayList<PaperMatchingEngine.Fill>();var audits=new ArrayList<Object>();
    var books=new HashMap<String,JsonNode>();boolean submitted=false;String target=s.path("targetQuote").path("token").asText();
    for(var rec:context.path("records")) {
      var row=rec.path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();
      String kind=row.path("kind").asText().substring(9);var data=row.path("data");
      var events=kind.equals("FRAME")?data.path("events"):node(List.of(Map.of("kind",kind,"data",data)));int ix=0;
      for(var ev:events) {
        String k=ev.path("kind").asText();var d=ev.path("data");if(k.equals("FEED_ERROR"))k="GAP";
        if(k.equals("BOOK")) {
          noFill(e.accept(k,at,d));String token=d.path("token").asText();long source=d.path("sourceMs").asLong(-1);
          if(source<0||source>at||at-source>2000||(books.containsKey(token)&&source<books.get(token).path("sourceMs").asLong()))books.remove(token);
          else books.put(token,d);
        } else if(k.equals("GAP")) {
          var affected=new HashSet<String>();d.path("tokens").forEach(t->affected.add(t.asText()));if(d.has("token"))affected.add(d.path("token").asText());
          if(affected.isEmpty()||affected.stream().anyMatch(pair::contains)){noFill(e.accept("GAP",at,node(Map.of("tokens",pair,"reason",d.path("reason").asText("unknown")))));pair.forEach(books::remove);}
          else noFill(e.accept("GAP",at,d));
        } else if(k.equals("TRADE")) {
          String key=seq+":"+ix;var b=labels.get(key);
          if(b!=null) {
            if(!seen.add(key))throw new IllegalArgumentException("Original binding consumed twice");
            var bound=binding(b,d,seq,ix,at,Set.copyOf(pair));
            var sources=new TreeMap<String,Long>();for(String t:pair)sources.put(t,books.containsKey(t)?books.get(t).path("sourceMs").asLong():-1L);
            long source=d.path("sourceMs").asLong();boolean causal=source>=0&&source<=at&&at-source<=2000;
            for(String t:pair)causal&=books.containsKey(t)&&!books.get(t).path("bids").isEmpty()&&!books.get(t).path("asks").isEmpty()
                &&at-sources.get(t)<=2000&&source>=sources.get(t);
            BigDecimal own=dec(s.path("targetQuote").path("price"));
            var priced=bound.portions().stream().filter(p->p.token().equals(target)&&p.buy()&&own.compareTo(p.price())>=0)
                .map(SettlementReplayLabels.Portion::quantity).reduce(BigDecimal.ZERO,BigDecimal::add);
            var u=e.acceptSettlement(at,d,bound);conditional.addAll(u.fills());
            audits.add(Map.of("seq",seq,"eventIndex",ix,"at",at,"sourceMs",d.path("sourceMs").asLong(),
                "pairBookSourcesBeforePrint",sources,"sourceNotOlderThanBothFreshBooks",causal,
                "targetPriceCompatibleQuantity",priced,"conditionalFills",u.fills()));
          } else {
            boolean relevant=(d.path("side").asText().equals("SELL")&&d.path("token").asText().equals(target))
                ||(d.path("side").asText().equals("BUY")&&pair.contains(d.path("token").asText())&&!d.path("token").asText().equals(target));
            if(submitted&&relevant&&d.path("sourceMs").asLong()>=s.path("activationDueMs").asLong()
                &&at<s.path("terminalMs").asLong())throw new IllegalStateException("Missing complete target-leg receipt label");
            noFill(e.accept("TICK",at,d)); // Never fall back to an unverified public aggregate.
          }
        } else if(k.equals("TICK"))noFill(e.accept(k,at,d));
        ix++;
      }
      if(seq==s.path("originalSequence").asLong()) {
        var q=s.path("targetQuote");e.accept("ORDER",at,node(Map.of("id","qw0-target-only","token",target,"side","BUY",
            "price",q.path("price").asText(),"size",q.path("quantity").asText())));submitted=true;
      }
    }
    if(!submitted||seen.size()!=39)throw new IllegalStateException("Incomplete source anchor/39 original labels");
    var out=new LinkedHashMap<String,Object>();out.put("scope","OPTIMISTIC_ISOLATED_QW0_TARGET_ONLY_NOT_STRATEGY_OR_ACCOUNT");
    out.put("state",s);out.put("consumedOriginalBindings",seen.size());out.put("diagnostics",e.diagnostics());
    out.put("actualComponentAllocationDiagnostics",e.settlementDiagnostics());out.put("bindingAudit",audits);
    out.put("conditionalModelFills",conditional);out.put("restingRiskCancellationOmitted",true);out.put("counterpartExecutionOmitted",true);
    out.put("actualBotFillsCreated",0);out.put("netPnlRecomputed",false);out.put("candidateAccountSimulated",false);
    out.put("independentPaperQualificationAllowed",false);out.put("liveAllowed",false);
    Files.writeString(Path.of(args[2]),M.writerWithDefaultPrettyPrinter().writeValueAsString(out)+"\n");
  }
}
