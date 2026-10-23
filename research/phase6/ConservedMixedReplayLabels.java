package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Separate offline-only adapter. Emits canonical matcher bindings, never orders or inventory.
 * Legacy CS-MINT-LAB0 and default/live paths are unchanged. Raw receipts are revalidated by exporter.
 */
final class ConservedMixedReplayLabels {
  private static final Set<String> EXCHANGES=Set.of(
      "0xe111180000d2663c0091e4f400237545b87b996b","0xe2222d279d744050d28e00520010520000310f59");
  private final Map<String,SettlementReplayLabels.Binding> bindings=new LinkedHashMap<>();
  private final Map<String,String> expectedTransactions=new HashMap<>();
  private final Set<String> transactions=new HashSet<>(),seen=new HashSet<>();
  private final Set<String> pair;
  private final ObjectMapper mapper;
  private int componentCount,suppressed;

  ConservedMixedReplayLabels(JsonNode root,ObjectMapper mapper) {
    this.mapper=mapper;
    if(root.path("schema").asInt()!=1 || !root.path("experiment").asText().equals("CONSERVED-MIXED-LAB0")
        || !root.path("partialLabels").asBoolean() || !root.path("adapterOnlyNotAccountReplay").asBoolean()
        || root.path("liveAllowed").asBoolean(true) || root.path("independentPaperQualificationAllowed").asBoolean(true)
        || root.path("candidateAccountSimulated").asBoolean(true) || root.path("netPnlRecomputed").asBoolean(true)
        || !root.path("modelFillsCreated").isIntegralNumber() || root.path("modelFillsCreated").asInt()!=0)
      throw new IllegalArgumentException("Offline adapter-only contract required");
    for(String field:List.of("logicalTapeSha256","contextLogicalSha256","contextCompressedSha256"))
      if(!root.path(field).asText().matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Missing source hash");
    var coverage=root.path("coverage");pair=pair(coverage.path("pair"));
    long after=integer(coverage,"afterMs"),through=integer(coverage,"throughMs");
    if(through<=after || !coverage.path("allOriginalPairObservationsWithinWindow").asBoolean()
        || !coverage.path("unknownScopedObservation").asText().equals("FAIL_CLOSED"))
      throw new IllegalArgumentException("Explicit closed coverage window required");
    long count=integer(root,"expectedBindingCount"),components=integer(root,"expectedComponentCount");
    if(!root.path("bindings").isArray() || count<1 || count>5000 || root.path("bindings").size()!=count || components<1 || components>50000)
      throw new IllegalArgumentException("Invalid bounded mixed-side manifest");
    var identities=new HashSet<String>();
    for(var n:root.path("bindings")) {
      long seq=integer(n,"seq"),index=integer(n,"eventIndex"),at=integer(n,"at"),source=integer(n,"sourceMs");
      String tx=text(n,"transactionHash"),token=text(n,"token"),side=side(n);
      if(seq<=0 || index>Integer.MAX_VALUE || at<=after || at>through || source>at || !pair(n.path("pair")).equals(pair)
          || !pair.contains(token) || !tx.matches("0x[0-9a-f]{64}") || !transactions.add(tx))
        throw new IllegalArgumentException("Invalid/duplicate mixed binding");
      boolean buy=side.equals("BUY");var portions=new ArrayList<SettlementReplayLabels.Portion>();
      BigInteger shares=BigInteger.ZERO,collateral=BigInteger.ZERO;JsonNode taker=null;long group=-1;String exchange=null;
      if(!n.path("matches").isArray() || n.path("matches").isEmpty())throw new IllegalArgumentException("No conserved matches");
      for(var row:n.path("matches")) {
        var m=row.path("maker");var t=row.path("taker");String ex=text(row,"exchange");long current=integer(row,"ordersMatchedLogIndex");
        if(!EXCHANGES.contains(ex) || !text(t,"token").equals(token) || !side(t).equals(side))throw new IllegalArgumentException("Untrusted taker identity");
        if(taker==null){taker=t;group=current;exchange=ex;}
        if(!t.equals(taker) || current!=group || !ex.equals(exchange))throw new IllegalArgumentException("Ambiguous conserved group");
        BigInteger making=positive(m,"makingRaw"),taking=positive(m,"takingRaw"),q,c,value;
        String makerToken=text(m,"token"),makerSide=side(m),route=text(row,"matchType");
        if(route.equals("DIRECT")) {
          if(!makerToken.equals(token)||makerSide.equals(side))throw new IllegalArgumentException("Invalid DIRECT route");
          q=buy?making:taking;c=buy?taking:making;value=c;
        } else if(route.equals(buy?"MINT":"MERGE")) {
          if(!pair.contains(makerToken)||makerToken.equals(token)||!makerSide.equals(side))throw new IllegalArgumentException("Invalid complementary route");
          q=buy?taking:making;c=buy?making:taking;value=q.subtract(c);
        } else throw new IllegalArgumentException("Unknown route");
        if(c.signum()<=0||c.compareTo(q)>=0)throw new IllegalArgumentException("Invalid component price");
        String id=ex+":"+tx+":"+group+":"+integer(m,"logIndex");
        if(!identities.add(id))throw new IllegalArgumentException("Duplicate actual component");
        shares=shares.add(q);collateral=collateral.add(value);
        portions.add(new SettlementReplayLabels.Portion(id,makerToken,makerSide.equals("BUY"),
            new BigDecimal(c).divide(new BigDecimal(q),28,makerSide.equals("BUY")?RoundingMode.CEILING:RoundingMode.FLOOR),new BigDecimal(q,6)));
      }
      if(!shares.equals(positive(taker,buy?"takingRaw":"makingRaw"))
          || !collateral.equals(positive(taker,buy?"makingRaw":"takingRaw"))
          || new BigDecimal(shares,6).compareTo(decimal(n,"size"))!=0)
        throw new IllegalArgumentException("Nonconserved shares/collateral");
      String hash=text(n,"publicTradeIdSha256");BigDecimal price=decimal(n,"price");
      if(!hash.matches("[0-9a-f]{64}") || price.compareTo(BigDecimal.ONE)>=0)throw new IllegalArgumentException("Invalid public trade hash/price");
      var binding=new SettlementReplayLabels.Binding(seq,(int)index,at,source,hash,token,side,price,decimal(n,"size"),pair,List.copyOf(portions));
      if(bindings.putIfAbsent(seq+":"+index,binding)!=null)throw new IllegalArgumentException("Duplicate original coordinate");
      expectedTransactions.put(seq+":"+index,tx);
    }
    componentCount=identities.size();
    if(componentCount!=components)throw new IllegalArgumentException("Incomplete actual components");
  }

  SettlementReplayLabels.Binding resolve(long seq,int index,long at,JsonNode data) {
    String raw=text(data,"tradeId"),key=seq+":"+index;var b=bindings.get(key);
    if(b!=null) {
      try {if(!mapper.readTree(raw).path("transaction_hash").asText().equals(expectedTransactions.get(key)))throw new IllegalArgumentException("Original transaction identity differs");}
      catch(java.io.IOException error){throw new IllegalArgumentException("Invalid original identity",error);}
      if(b.at()!=at || b.source()!=integer(data,"sourceMs") || !b.tradeHash().equals(hash(raw))
          || !b.token().equals(text(data,"token")) || !b.side().equals(side(data))
          || b.price().compareTo(decimal(data,"price"))!=0 || b.size().compareTo(decimal(data,"size"))!=0)
        throw new IllegalArgumentException("Original mixed trade binding differs");
      if(!seen.add(key))throw new IllegalArgumentException("Binding consumed twice");
      return b;
    }
    try {
      if(raw.startsWith("{") && transactions.contains(mapper.readTree(raw).path("transaction_hash").asText())) {
        suppressed++;
        return new SettlementReplayLabels.Binding(seq,index,at,integer(data,"sourceMs"),"","","",BigDecimal.ONE,BigDecimal.ONE,Set.of(),List.of());
      }
    } catch(java.io.IOException error){throw new IllegalArgumentException("Invalid original identity",error);}
    if(pair.contains(data.path("token").asText()))throw new IllegalArgumentException("Unknown scoped observation; incomplete coverage is not zero");
    return null;
  }

  void requireConsumed(){if(seen.size()!=bindings.size())throw new IllegalStateException("Incomplete original binding consumption");}
  Map<String,Object> report(){return Map.of("experiment","CONSERVED-MIXED-LAB0","bindings",bindings.size(),"consumedBindings",seen.size(),
      "actualComponents",componentCount,"duplicateAggregateSuppressed",suppressed,"adapterOnlyNotAccountReplay",true,
      "candidateAccountSimulated",false,"independentPaperQualificationAllowed",false,"liveAllowed",false);}
  private static String text(JsonNode n,String k){if(!n.path(k).isTextual()||n.path(k).asText().isBlank())throw new IllegalArgumentException("Missing text "+k);return n.path(k).asText();}
  private static String side(JsonNode n){String s=text(n,"side");if(!s.equals("BUY")&&!s.equals("SELL"))throw new IllegalArgumentException("Invalid side");return s;}
  private static long integer(JsonNode n,String k){if(!n.path(k).isIntegralNumber()||!n.path(k).canConvertToLong()||n.path(k).asLong()<0)throw new IllegalArgumentException("Nonnegative integer required "+k);return n.path(k).asLong();}
  private static BigInteger positive(JsonNode n,String k){if(!n.path(k).isIntegralNumber()||n.path(k).bigIntegerValue().signum()<=0||n.path(k).bigIntegerValue().bitLength()>256)throw new IllegalArgumentException("Positive uint256 raw integer required "+k);return n.path(k).bigIntegerValue();}
  private static BigDecimal decimal(JsonNode n,String k){BigDecimal d=new BigDecimal(n.path(k).asText());if(d.signum()<=0)throw new IllegalArgumentException("Invalid decimal "+k);return d;}
  private static Set<String> pair(JsonNode n){if(!n.isArray()||n.size()!=2||!n.get(0).isTextual()||!n.get(1).isTextual()||n.get(0).asText().isBlank()||n.get(1).asText().isBlank()||n.get(0).equals(n.get(1)))throw new IllegalArgumentException("Binary pair required");return Set.of(n.get(0).asText(),n.get(1).asText());}
  static String hash(String raw){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8)));}catch(java.security.NoSuchAlgorithmException e){throw new IllegalStateException(e);}}
}
