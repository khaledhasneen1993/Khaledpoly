package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.io.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Offline environment labels. No runtime configuration, wallet, network or strategy features. */
final class SettlementReplayLabels {
  record Portion(String identity, String token, boolean buy, BigDecimal price, BigDecimal quantity) {}
  record Binding(long seq, int index, long at, long source, String tradeHash, String token,
      String side, BigDecimal price, BigDecimal size, Set<String> pair, List<Portion> portions) {}
  private static final Set<String> EXCHANGES = Set.of(
      "0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59");
  private final Map<String, Binding> bindings = new HashMap<>();
  private final Set<String> transactions = new HashSet<>(), seen = new HashSet<>();
  private final ObjectMapper mapper;
  final String logicalSha;
  final String labelsSha;

  SettlementReplayLabels(JsonNode root, ObjectMapper mapper, String labelsSha) {
    this.mapper=mapper; this.labelsSha=labelsSha;
    if (!root.path("experiment").asText().equals("CS-MINT-LAB0")
        || !root.path("partialLabels").asBoolean() || root.path("liveAllowed").asBoolean(true))
      throw new IllegalArgumentException("Only partial, research-only CS-MINT-LAB0 labels supported");
    logicalSha=root.path("logicalTapeSha256").asText();
    if (!logicalSha.matches("[0-9a-f]{64}") || !root.path("bindings").isArray()
        || root.path("bindings").isEmpty() || root.path("bindings").size()>100)
      throw new IllegalArgumentException("Invalid bounded label manifest");
    var identities=new HashSet<String>();
    for (var n:root.path("bindings")) {
      var pair=new HashSet<String>(); n.path("pair").forEach(t->pair.add(t.asText()));
      String tx=n.path("transactionHash").asText(), token=n.path("token").asText();
      if (pair.size()!=2 || !pair.contains(token) || !n.path("side").asText().equals("BUY")
          || !tx.matches("0x[0-9a-f]{64}")) throw new IllegalArgumentException("Invalid binary BUY binding");
      var parts=new ArrayList<Portion>(); BigInteger shares=BigInteger.ZERO, cost=BigInteger.ZERO;
      JsonNode taker=null;
      long group=-1;
      String groupExchange=null;
      for (var row:n.path("matches")) {
        var m=row.path("maker");var t=row.path("taker");String exchange=row.path("exchange").asText();
        long currentGroup=row.path("ordersMatchedLogIndex").asLong(-1);
        if (!EXCHANGES.contains(exchange) || currentGroup<0 || m.path("logIndex").asLong(-1)<0
            || !t.path("token").asText().equals(token) || !t.path("side").asText().equals("BUY"))
          throw new IllegalArgumentException("Untrusted settlement group");
        if (taker==null) { taker=t;group=currentGroup;groupExchange=exchange; }
        if (!t.equals(taker) || currentGroup!=group || !exchange.equals(groupExchange))
          throw new IllegalArgumentException("Ambiguous matching group");
        BigInteger making=positive(m,"makingRaw"),taking=positive(m,"takingRaw"),q,c;
        boolean mint=row.path("matchType").asText().equals("MINT");
        if (mint) {
          if (!m.path("side").asText().equals("BUY") || !pair.contains(m.path("token").asText())
              || m.path("token").asText().equals(token)) throw new IllegalArgumentException("Invalid MINT identity");
          q=taking;c=making;cost=cost.add(q.subtract(c));
        } else {
          if (!row.path("matchType").asText().equals("DIRECT") || !m.path("side").asText().equals("SELL")
              || !m.path("token").asText().equals(token)) throw new IllegalArgumentException("Invalid DIRECT identity");
          q=making;c=taking;cost=cost.add(c);
        }
        if (c.compareTo(q)>=0) throw new IllegalArgumentException("Invalid settlement price");
        String identity=exchange+":"+tx+":"+group+":"+m.path("logIndex").asLong();
        if (!identities.add(identity)) throw new IllegalArgumentException("Duplicate maker component");
        shares=shares.add(q);
        parts.add(new Portion(identity,m.path("token").asText(),mint,
            new BigDecimal(c).divide(new BigDecimal(q),28,RoundingMode.HALF_EVEN),new BigDecimal(q,6)));
      }
      BigDecimal size=decimal(n,"size");
      if (taker==null || !shares.equals(positive(taker,"takingRaw")) || !cost.equals(positive(taker,"makingRaw"))
          || new BigDecimal(shares,6).compareTo(size)!=0) throw new IllegalArgumentException("Nonconserved receipt group");
      var b=new Binding(n.path("seq").asLong(-1),n.path("eventIndex").asInt(-1),n.path("at").asLong(-1),
          n.path("sourceMs").asLong(-1),n.path("publicTradeIdSha256").asText(),token,"BUY",decimal(n,"price"),
          size,Set.copyOf(pair),List.copyOf(parts));
      if (b.seq<=0 || b.index<0 || b.source<0 || b.at<b.source || b.price.compareTo(BigDecimal.ONE)>=0
          || !b.tradeHash.matches("[0-9a-f]{64}")
          || bindings.putIfAbsent(b.seq+":"+b.index,b)!=null || !transactions.add(tx))
        throw new IllegalArgumentException("Invalid or duplicate frozen binding");
    }
  }

  static SettlementReplayLabels load(Path path, ObjectMapper mapper) throws Exception {
    if (Files.size(path)>2_000_000) throw new IllegalArgumentException("Oversized label file");
    return new SettlementReplayLabels(mapper.readTree(Files.readString(path)),mapper,ClosedLoopReplay.sha256(path));
  }

  private static BigInteger positive(JsonNode n,String key) {
    var value=n.path(key);
    if (!value.isIntegralNumber() || value.bigIntegerValue().signum()<=0)
      throw new IllegalArgumentException("Invalid raw integer amount");
    return value.bigIntegerValue();
  }

  private static BigDecimal decimal(JsonNode n,String key) {
    var value=new BigDecimal(n.path(key).asText());
    if (value.signum()<=0) throw new IllegalArgumentException("Invalid positive decimal");
    return value;
  }

  Binding resolve(long seq,int index,long at,JsonNode data) {
    var b=bindings.get(seq+":"+index);
    String raw=data.path("tradeId").asText();
    if (b!=null) {
      String hash=HexFormat.of().formatHex(digest(raw.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
      if (b.at!=at || b.source!=data.path("sourceMs").asLong(-1) || !b.tradeHash.equals(hash)
          || !b.token.equals(data.path("token").asText()) || !b.side.equals(data.path("side").asText())
          || b.price.compareTo(decimal(data,"price"))!=0 || b.size.compareTo(decimal(data,"size"))!=0)
        throw new IllegalArgumentException("Frozen label binding does not match original trade");
      if (!seen.add(seq+":"+index)) throw new IllegalArgumentException("Binding consumed twice");
      return b;
    }
    try {
      if (raw.startsWith("{") && transactions.contains(mapper.readTree(raw).path("transaction_hash").asText()))
        return new Binding(seq,index,at,data.path("sourceMs").asLong(-1),"","","",BigDecimal.ONE,
            BigDecimal.ONE,Set.of(),List.of()); // Covered tx: suppress other aggregate observations, never add volume.
    } catch (java.io.IOException error) { throw new IllegalArgumentException("Invalid recorded trade identity",error); }
    return null;
  }

  void verifyTape(Path path) throws Exception {
    var digest=MessageDigest.getInstance("SHA-256");
    try (InputStream file=Files.newInputStream(path);
        InputStream input=path.toString().endsWith(".gz")?new GZIPInputStream(file,65536):file) {
      byte[] buffer=new byte[65536];int count;
      while ((count=input.read(buffer))!=-1) digest.update(buffer,0,count);
    }
    if (!HexFormat.of().formatHex(digest.digest()).equals(logicalSha))
      throw new IllegalArgumentException("Labels belong to a different logical tape");
  }

  static byte[] digest(byte[] bytes) {
    try { return MessageDigest.getInstance("SHA-256").digest(bytes); }
    catch (java.security.NoSuchAlgorithmException error) { throw new IllegalStateException(error); }
  }

  Map<String,Object> report() {
    return Map.of("experiment","CS-MINT-LAB0","labelBindings",bindings.size(),"consumedBindings",seen.size(),
        "partialLabels",true,"logicalTapeSha256",logicalSha,"labelsSha256",labelsSha,
        "independentPaperQualificationAllowed",false,"liveAllowed",false);
  }

  void requireConsumed() {
    if (seen.size()!=bindings.size()) throw new IllegalStateException("Not all frozen label bindings matched this replay");
  }
}
