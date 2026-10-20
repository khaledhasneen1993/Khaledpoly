package com.polybot.hft.paper;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.*;
import java.io.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.*;
import java.util.*;

/** Research-only identity facts, NEVER settlement labels or a no-order witness.
 * The complete frozen original census is mandatory even for subset diagnostics.
 * No service registration, default policy changes, or runtime skipping.
 */
final class CompleteSourceIdentityIndex {
  static final String INDEX_SHA="1f8d1d953f3755b8244c7ac11f7a3f72ccd8d73b1c9807b7cec417b6b710c1c2";
  static final int COUNT=16317, MAX_BYTES=16*1024*1024;
  enum Mode { FULL_ORIGINAL_SEQUENCE, RETAINED_PREIMAGE_SUBSET_ONLY }
  record Identity(long seq,int index,long at,long source,String token,String side,
                  BigDecimal price,BigDecimal size,String rawHash,String transaction) {}
  private record Key(long seq,int index) {}
  private final List<Identity> rows;
  private final Map<Key,Integer> positions;
  private final Mode mode;
  private final ObjectMapper mapper=new ObjectMapper().enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
      .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
  private int last=-1,consumed;
  private boolean failed;

  CompleteSourceIdentityIndex(Path path) throws IOException {this(path,Mode.FULL_ORIGINAL_SEQUENCE);}
  CompleteSourceIdentityIndex(Path path,Mode mode) throws IOException {
    this.mode=Objects.requireNonNull(mode);
    byte[] bytes;
    try(var input=Files.newInputStream(path)){bytes=input.readNBytes(MAX_BYTES+1);}
    if(bytes.length>MAX_BYTES||!sha(bytes).equals(INDEX_SHA))throw new IllegalArgumentException("Changed/bounded complete original index");
    String raw=new String(bytes,StandardCharsets.UTF_8);
    if(!Arrays.equals(raw.getBytes(StandardCharsets.UTF_8),bytes)||!raw.endsWith("\n"))throw new IllegalArgumentException("Exact original UTF8 stream required");
    String[] lines=raw.split("\n",-1);
    if(lines.length!=COUNT+1)throw new IllegalArgumentException("Complete16317 identity stream required");
    var parsed=new ArrayList<Identity>();var keys=new HashMap<Key,Integer>();
    var txs=new HashSet<String>();var hashes=new HashSet<String>();long prevSeq=-1,prevAt=-1;int prevIndex=-1;
    Set<String> fields=Set.of("seq","eventIndex","at","sourceMs","token","condition","side","price","size","publicTradeIdSha256","transactionHash","coverage");
    Set<String> coverage=Set.of("BOUND_CONSERVED_GROUP","MISSING_SCOPED_PAIR_LABEL","OTHER_MARKET_UNBOUND_NO_AGGREGATE_FALLBACK","UNKNOWN_MARKET_UNBOUND");
    for(int i=0;i<COUNT;i++) {
      if(lines[i].getBytes(StandardCharsets.UTF_8).length>8192)throw new IllegalArgumentException("Oversized identity");
      JsonNode n=mapper.readTree(lines[i]);var names=new HashSet<String>();n.fieldNames().forEachRemaining(names::add);
      if(!names.equals(fields))throw new IllegalArgumentException("Exact identity schema required");
      long seq=integer(n,"seq"),idx=integer(n,"eventIndex"),at=integer(n,"at"),source=integer(n,"sourceMs");
      String token=text(n,"token"),side=text(n,"side"),tx=text(n,"transactionHash"),hash=text(n,"publicTradeIdSha256");
      if(seq<1||seq>=6163831||idx>Integer.MAX_VALUE||seq<prevSeq||seq==prevSeq&&idx<=prevIndex
          ||at<prevAt||at<1792269582615L||at>1792276779073L||!token.matches("[0-9]+")
          ||!text(n,"condition").matches("0x[0-9a-f]{64}")||!Set.of("BUY","SELL").contains(side)
          ||!coverage.contains(text(n,"coverage"))||!tx.matches("0x[0-9a-f]{64}")||!hash.matches("[0-9a-f]{64}")
          ||!txs.add(tx)||!hashes.add(hash))throw new IllegalArgumentException("Original identity/order/global uniqueness differs");
      BigDecimal price=decimal(n,"price"),size=decimal(n,"size");
      if(price.compareTo(BigDecimal.ONE)>=0)throw new IllegalArgumentException("Invalid original price");
      Key key=new Key(seq,(int)idx);if(keys.putIfAbsent(key,i)!=null)throw new IllegalArgumentException("Duplicate coordinate");
      parsed.add(new Identity(seq,(int)idx,at,source,token,side,price,size,hash,tx));prevSeq=seq;prevIndex=(int)idx;prevAt=at;
    }
    rows=List.copyOf(parsed);positions=Map.copyOf(keys);
  }

  synchronized Identity consume(long seq,int index,long at,JsonNode trade) {
    if(failed)throw new IllegalStateException("Source index poisoned; no continuation");
    try {
      Integer position=positions.get(new Key(seq,index));
      if(position==null||position<=last||mode==Mode.FULL_ORIGINAL_SEQUENCE&&position!=last+1)
        throw new IllegalArgumentException("Unknown/duplicate/reversed/missing original identity");
      Identity row=rows.get(position);String raw=text(trade,"tradeId");
      byte[] bytes=raw.getBytes(StandardCharsets.UTF_8);
      if(bytes.length>1024*1024||!new String(bytes,StandardCharsets.UTF_8).equals(raw))
        throw new IllegalArgumentException("Bounded exact original UTF8 bytes required");
      if(row.at()!=at||row.source()!=integer(trade,"sourceMs")||!row.token().equals(text(trade,"token"))
          ||!row.side().equals(text(trade,"side"))||row.price().compareTo(decimal(trade,"price"))!=0
          ||row.size().compareTo(decimal(trade,"size"))!=0||!row.rawHash().equals(sha(bytes))
          ||!row.transaction().equals(text(mapper.readTree(raw),"transaction_hash")))
        throw new IllegalArgumentException("Exact original identity/preimage mismatch");
      last=position;consumed++;return row;
    }catch(IOException|RuntimeException error){failed=true;throw new IllegalArgumentException("Fail-closed original identity consumption",error);}
  }
  synchronized void requireComplete() {
    if(failed||mode!=Mode.FULL_ORIGINAL_SEQUENCE||consumed!=COUNT){failed=true;throw new IllegalStateException("Incomplete source; no full replay proof");}
  }
  synchronized Map<String,Object> report() {
    return Map.of("originalIdentities",COUNT,"consumedOriginalPreimages",consumed,"failed",failed,
        "subsetPreimageTestOnly",mode==Mode.RETAINED_PREIMAGE_SUBSET_ONLY,
        "completeOriginalConsumption",!failed&&mode==Mode.FULL_ORIGINAL_SEQUENCE&&consumed==COUNT,
        "settlementRoutesValidatedByIndex",false,"runtimeSkipAuthorized",false,"identitiesSha256",INDEX_SHA);
  }
  private static String text(JsonNode n,String key){if(!n.path(key).isTextual()||n.path(key).asText().isBlank())throw new IllegalArgumentException("Text required "+key);return n.path(key).asText();}
  private static long integer(JsonNode n,String key){var v=n.path(key);if(!v.isIntegralNumber()||!v.canConvertToLong()||v.asLong()<0)throw new IllegalArgumentException("Nonnegative integer required "+key);return v.asLong();}
  private static BigDecimal decimal(JsonNode n,String key){var v=n.path(key);if(!v.isNumber()&&!v.isTextual()||v.asText().length()>128)throw new IllegalArgumentException("Bounded decimal required "+key);BigDecimal d=new BigDecimal(v.asText());if(d.signum()<=0)throw new IllegalArgumentException("Positive decimal required "+key);return d;}
  static String sha(byte[] bytes){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(NoSuchAlgorithmException error){throw new IllegalStateException(error);}}
}
