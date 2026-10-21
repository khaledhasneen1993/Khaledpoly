package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Strict PARTIAL offline pool. Unknown observations NEVER return null/zero/aggregate fallback.
 * Separate from immutable legacy window adapters; no default/service/live registration.
 */
final class ConservedReceiptPool implements OfflineSessionLabels {
  private static final Set<String> EXCHANGES=Set.of("0xe111180000d2663c0091e4f400237545b87b996b","0xe2222d279d744050d28e00520010520000310f59");
  private record Key(long seq,int index) {}
  private final Map<Key,SettlementReplayLabels.Binding> bindings=new LinkedHashMap<>();
  private final Map<Key,String> transactions=new HashMap<>();
  private final Set<Key> consumed=new HashSet<>();
  private final ObjectMapper mapper;
  private final int components;
  private boolean failed;

  ConservedReceiptPool(JsonNode root,ObjectMapper mapper) {
    this.mapper=mapper;
    String scope=text(root,"scope");boolean multi=scope.equals("PARTIAL_MULTI_MARKET_RECEIPT_POOL_NOT_EXECUTION_MANIFEST");
    if(integer(root,"schema")!=1 || !text(root,"experiment").equals("CONSERVED-RECEIPT-POOL0")
        || !(scope.equals("PARTIAL_SINGLE_MARKET_RECEIPT_POOL_NOT_EXECUTION_MANIFEST")||multi)
        || !text(root,"unknownScopedObservation").equals("FAIL_CLOSED"))throw new IllegalArgumentException("Partial offline pool required");
    for(String k:List.of("partialLabels","metadataUsedOnlyForStaticPairIdentityNotDecisionFreshness","nativeSourceIdentityRecheckRequired"))flag(root,k,true);
    for(String k:List.of("allOriginalPairObservationsWithinWindow","nativePoolConsumerImplemented","netPnlRecomputed","candidateAccountSimulated",
        "fullAccountReplayAuthorized","independentPaperQualificationAllowed","liveAllowed"))flag(root,k,false);
    if(integer(root,"newPublicReads")!=0 || integer(root,"modelFillsCreated")!=0 || !text(root,"decision").equals("NO_GO"))throw new IllegalArgumentException("No execution or new reads allowed");
    for(String k:List.of("logicalTapeSha256","sourceCensusArtifactZipSha256","sourceAllTradeIdentitiesSha256"))hashField(root,k);
    var metadata=root.path("metadataIdentityReference");flag(metadata,"negativeRisk",false);hashField(metadata,"sha256");
    String condition=text(metadata,"condition");if(!condition.matches("0x[0-9a-f]{64}"))throw new IllegalArgumentException("Recorded condition required");
    Set<String> pair=pair(metadata.path("pair"));
    var marketPairs=new HashMap<String,Set<String>>();marketPairs.put(condition,pair);
    if(multi){flag(root,"multiMarketBindings",true);var declared=root.path("bindingMarketPairs");if(!declared.isObject()||declared.size()<1||declared.size()>20)throw new IllegalArgumentException("Bounded market-pair map required");for(var it=declared.fields();it.hasNext();){var e=it.next();var declaredPair=pair(e.getValue());var prior=marketPairs.putIfAbsent(e.getKey(),declaredPair);if(!e.getKey().matches("0x[0-9a-f]{64}")||prior!=null&&!prior.equals(declaredPair))throw new IllegalArgumentException("Conflicting market pair");}}
    long count=integer(root,"expectedBindingCount"),expected=integer(root,"expectedComponentCount");
    if(count<1||count>5000||expected<1||expected>50000||!root.path("bindings").isArray()||root.path("bindings").size()!=count)throw new IllegalArgumentException("Bounded nonempty pool required");
    Set<String> ids=new HashSet<>(),txs=new HashSet<>();long lastSeq=-1,lastAt=-1;int lastIndex=-1;
    for(var n:root.path("bindings")) {
      long seq=integer(n,"seq"),idx=integer(n,"eventIndex"),at=integer(n,"at"),source=integer(n,"sourceMs");
      String token=text(n,"token"),side=side(n),tx=text(n,"transactionHash"),bindingCondition=text(n,"condition");Set<String> bindingPair=pair(n.path("pair"));
      if(seq<=0||idx>Integer.MAX_VALUE||source>at||at<lastAt||seq<lastSeq||seq==lastSeq&&idx<=lastIndex
          ||!marketPairs.containsKey(bindingCondition)||!marketPairs.get(bindingCondition).equals(bindingPair)||!bindingPair.contains(token)
          ||!tx.matches("0x[0-9a-f]{64}")||!txs.add(tx))throw new IllegalArgumentException("Invalid/duplicate/unordered pool identity");
      lastSeq=seq;lastIndex=(int)idx;lastAt=at;boolean buy=side.equals("BUY");
      var portions=new ArrayList<SettlementReplayLabels.Portion>();JsonNode taker=null;String exchange=null;long group=-1;
      BigInteger shares=BigInteger.ZERO,collateral=BigInteger.ZERO;
      if(!n.path("matches").isArray()||n.path("matches").isEmpty())throw new IllegalArgumentException("Missing conserved components");
      for(var row:n.path("matches")) {
        var maker=row.path("maker");var currentTaker=row.path("taker");String ex=text(row,"exchange");long gi=integer(row,"ordersMatchedLogIndex");
        if(!EXCHANGES.contains(ex)||!text(currentTaker,"token").equals(token)||!side(currentTaker).equals(side))throw new IllegalArgumentException("Untrusted taker/exchange");
        if(taker==null){taker=currentTaker;exchange=ex;group=gi;}
        if(!taker.equals(currentTaker)||!exchange.equals(ex)||group!=gi)throw new IllegalArgumentException("Ambiguous conserved group");
        String mt=text(maker,"token"),ms=side(maker),route=text(row,"matchType");
        BigInteger making=positive(maker,"makingRaw"),taking=positive(maker,"takingRaw"),q,c,value;
        if(route.equals("DIRECT")) {
          if(!mt.equals(token)||ms.equals(side))throw new IllegalArgumentException("Invalid DIRECT route");
          q=buy?making:taking;c=buy?taking:making;value=c;
        } else if(route.equals(buy?"MINT":"MERGE")) {
          if(!bindingPair.contains(mt)||mt.equals(token)||!ms.equals(side))throw new IllegalArgumentException("Invalid complementary route");
          q=buy?taking:making;c=buy?making:taking;value=q.subtract(c);
        } else throw new IllegalArgumentException("Unsupported route");
        if(c.signum()<=0||c.compareTo(q)>=0)throw new IllegalArgumentException("Invalid component price");
        String id=ex+":"+tx+":"+group+":"+integer(maker,"logIndex");
        if(!ids.add(id))throw new IllegalArgumentException("Duplicate actual component");
        shares=shares.add(q);collateral=collateral.add(value);
        portions.add(new SettlementReplayLabels.Portion(id,mt,ms.equals("BUY"),new BigDecimal(c).divide(new BigDecimal(q),28,
            ms.equals("BUY")?RoundingMode.CEILING:RoundingMode.FLOOR),new BigDecimal(q,6)));
      }
      if(!shares.equals(positive(taker,buy?"takingRaw":"makingRaw"))||!collateral.equals(positive(taker,buy?"makingRaw":"takingRaw"))
          ||new BigDecimal(shares,6).compareTo(decimal(n,"size"))!=0)throw new IllegalArgumentException("Nonconserved shares/collateral");
      String hash=hashField(n,"publicTradeIdSha256");BigDecimal price=decimal(n,"price");
      if(price.compareTo(BigDecimal.ONE)>=0)throw new IllegalArgumentException("Invalid public observation price");
      Key key=new Key(seq,(int)idx);var binding=new SettlementReplayLabels.Binding(seq,(int)idx,at,source,hash,token,side,price,decimal(n,"size"),bindingPair,List.copyOf(portions));
      if(bindings.putIfAbsent(key,binding)!=null)throw new IllegalArgumentException("Duplicate coordinate");transactions.put(key,tx);
    }
    components=ids.size();if(components!=expected)throw new IllegalArgumentException("Incomplete component count");
  }

  public synchronized SettlementReplayLabels.Binding resolve(long seq,int index,long at,JsonNode trade) {
    if(failed)throw new IllegalStateException("Partial pool failed; no continuation");
    try {
      Key key=new Key(seq,index);var b=bindings.get(key);
      if(b==null)throw new IllegalArgumentException("Unknown original observation; incomplete pool is not zero");
      String raw=text(trade,"tradeId");JsonNode identity=mapper.readTree(raw);
      if(b.at()!=at||b.source()!=integer(trade,"sourceMs")||!b.token().equals(text(trade,"token"))||!b.side().equals(side(trade))
          ||b.price().compareTo(decimal(trade,"price"))!=0||b.size().compareTo(decimal(trade,"size"))!=0
          ||!b.tradeHash().equals(hash(raw))||!transactions.get(key).equals(text(identity,"transaction_hash")))throw new IllegalArgumentException("Original pool observation identity differs");
      if(!consumed.add(key))throw new IllegalArgumentException("Pool binding consumed twice");
      return b;
    } catch(java.io.IOException|RuntimeException error) {
      failed=true;throw new IllegalArgumentException("Fail-closed pool resolution",error);
    }
  }
  public synchronized void requireConsumed(){if(failed||consumed.size()!=bindings.size())throw new IllegalStateException("Incomplete/failed pool consumption");}
  public Profile profile(){return Profile.MIXED_BINDING_BRIDGE0;}
  public synchronized Map<String,Object> report(){var r=new LinkedHashMap<String,Object>();r.put("experiment","CONSERVED-RECEIPT-POOL0");r.put("bindings",bindings.size());r.put("consumedBindings",consumed.size());r.put("actualComponents",components);
    r.put("failed",failed);r.put("strictPartialPool",true);r.put("nativePartialPoolReaderImplemented",true);r.put("aggregateFallbackAllowed",false);r.put("fullOriginalTapeCoverageProven",false);
    r.put("fullAccountReplayAuthorized",false);r.put("independentPaperQualificationAllowed",false);r.put("liveAllowed",false);return r;}
  private static void flag(JsonNode n,String k,boolean expected){if(!n.path(k).isBoolean()||n.path(k).asBoolean()!=expected)throw new IllegalArgumentException("Invalid scope flag "+k);}
  private static String text(JsonNode n,String k){if(!n.path(k).isTextual()||n.path(k).asText().isBlank())throw new IllegalArgumentException("Missing text "+k);return n.path(k).asText();}
  private static String hashField(JsonNode n,String k){String s=text(n,k);if(!s.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Missing hash "+k);return s;}
  private static String side(JsonNode n){String s=text(n,"side");if(!s.equals("BUY")&&!s.equals("SELL"))throw new IllegalArgumentException("Invalid side");return s;}
  private static long integer(JsonNode n,String k){if(!n.path(k).isIntegralNumber()||!n.path(k).canConvertToLong()||n.path(k).asLong()<0)throw new IllegalArgumentException("Nonnegative integer required "+k);return n.path(k).asLong();}
  private static BigInteger positive(JsonNode n,String k){if(!n.path(k).isIntegralNumber()||n.path(k).bigIntegerValue().signum()<=0||n.path(k).bigIntegerValue().bitLength()>256)throw new IllegalArgumentException("Positive uint256 required "+k);return n.path(k).bigIntegerValue();}
  private static BigDecimal decimal(JsonNode n,String k){BigDecimal d=new BigDecimal(n.path(k).asText());if(d.signum()<=0)throw new IllegalArgumentException("Positive decimal required "+k);return d;}
  private static Set<String> pair(JsonNode n){if(!n.isArray()||n.size()!=2||!n.get(0).isTextual()||!n.get(1).isTextual()||n.get(0).asText().isBlank()||n.get(1).asText().isBlank()||n.get(0).equals(n.get(1)))throw new IllegalArgumentException("Binary pair required");return Set.of(n.get(0).asText(),n.get(1).asText());}
  static String hash(String raw){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8)));}catch(java.security.NoSuchAlgorithmException e){throw new IllegalStateException(e);}}
}
