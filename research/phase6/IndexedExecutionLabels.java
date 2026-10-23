package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import java.math.BigDecimal;
import java.nio.file.*;
import java.util.*;

/** Explicit DEVELOPMENT-only source index + partial real labels + atomic empty witness.
 * Unknown observations NEVER resolve as null/empty labels or public trade volume.
 */
final class IndexedExecutionLabels implements OfflineSessionLabels {
  private record Key(long seq,int index) {}
  private sealed interface Route permits Known,Unbound {}
  private record Known(SettlementReplayLabels.Binding binding) implements Route {}
  private record Unbound() implements Route {}
  static final class Observation {
    private final IndexedExecutionLabels owner;private final Route route;
    private final CompleteSourceIdentityIndex.Identity identity;private boolean used;
    private final JsonNode trade;
    private Observation(IndexedExecutionLabels owner,Route route,CompleteSourceIdentityIndex.Identity identity,JsonNode trade){this.owner=owner;this.route=route;this.identity=identity;this.trade=trade;}
    JsonNode verifiedTrade(){return trade.deepCopy();}
  }
  private final ConservedReceiptPool pool;
  private final CompleteSourceIdentityIndex index;
  private final Set<Key> known;
  private ResearchSession session;private PaperMatchingEngine matcher;
  private boolean failed;
  private long knownApplied,knownExpired,unknownClock,unknownExpired;
  private BigDecimal expiredKnownQuantity=BigDecimal.ZERO,observedUnknownPublicSize=BigDecimal.ZERO;
  private Map<String,Object> last=Map.of();

  IndexedExecutionLabels(Path poolPath,Path indexPath,ObjectMapper mapper)throws Exception {
    byte[] bytes;try(var input=Files.newInputStream(poolPath)){bytes=input.readNBytes(8*1024*1024+1);}
    if(bytes.length>8*1024*1024||!CompleteSourceIdentityIndex.sha(bytes).equals("c41eda69ffe03ed06835a9fac403401f0d68aa3fa92b019bf37d410a212ee231"))
      throw new IllegalArgumentException("Exact frozen real643 pool required");
    JsonNode root=mapper.readTree(bytes);pool=new ConservedReceiptPool(root,mapper);
    index=new CompleteSourceIdentityIndex(indexPath);var keys=new HashSet<Key>();
    for(var row:root.path("bindings"))keys.add(new Key(row.path("seq").asLong(),row.path("eventIndex").asInt()));known=Set.copyOf(keys);
  }
  synchronized void attach(ResearchSession owner,PaperMatchingEngine engine){
    if(!Thread.holdsLock(owner)||!Thread.holdsLock(engine)||session!=null||failed||index.report().get("subsetPreimageTestOnly").equals(true))throw new IllegalStateException("One fresh atomic full index session required");
    session=Objects.requireNonNull(owner);matcher=Objects.requireNonNull(engine);
  }
  synchronized Observation observe(long seq,int eventIndex,long at,JsonNode trade){
    if(failed||session==null||!Thread.holdsLock(session)){failed=true;throw new IllegalStateException("Indexed execution failed/unattached/non-atomic");}
    try {
      JsonNode snapshot=trade.deepCopy();
      last=Map.of("seq",seq,"eventIndex",eventIndex,"at",at,"observation",snapshot.deepCopy());
      var identity=index.consume(seq,eventIndex,at,snapshot);
      Route route=known.contains(new Key(seq,eventIndex))?new Known(pool.resolve(seq,eventIndex,at,snapshot)):new Unbound();
      return new Observation(this,route,identity,snapshot);
    }catch(RuntimeException error){failed=true;throw error;}
  }
  synchronized PaperMatchingEngine.Update advance(Observation observation,boolean expired,long at){
    if(!Thread.holdsLock(session)||failed||observation==null||observation.owner!=this||observation.used){failed=true;throw new IllegalStateException("Invalid/reused/non-atomic indexed observation");}
    observation.used=true;
    try {
      JsonNode trade=observation.trade;
      if(observation.identity.at()!=at||!observation.identity.rawHash().equals(CompleteSourceIdentityIndex.sha(trade.path("tradeId").asText().getBytes(java.nio.charset.StandardCharsets.UTF_8))))
        throw new IllegalArgumentException("Prepared original identity changed");
      if(observation.route instanceof Known route){
        if(!expired){var update=matcher.acceptSettlement(at,trade,route.binding());knownApplied++;return update;}
        var update=matcher.accept("TICK",at,trade);knownExpired++;
        expiredKnownQuantity=expiredKnownQuantity.add(route.binding().portions().stream().map(SettlementReplayLabels.Portion::quantity).reduce(BigDecimal.ZERO,BigDecimal::add));return update;
      }
      return session.withResearchNoOrderWitness(witness->{
        witness.requireValid();var update=matcher.accept("TICK",at,trade);
        if(!update.fills().isEmpty())throw new IllegalStateException("Unexpected fill under empty atomic witness");
        unknownClock++;if(expired)unknownExpired++;
        observedUnknownPublicSize=observedUnknownPublicSize.add(observation.identity.size());return update;
      });
    }catch(RuntimeException error){failed=true;throw error;}
  }
  public synchronized SettlementReplayLabels.Binding resolve(long seq,int eventIndex,long at,JsonNode trade){failed=true;throw new IllegalStateException("Explicit indexed execution required; no unknown label fallback");}
  public Profile profile(){return Profile.MIXED_BINDING_BRIDGE0;}
  public synchronized void requireConsumed(){
    if(failed)throw new IllegalStateException("Failed indexed source execution");
    try{index.requireComplete();pool.requireConsumed();}catch(RuntimeException error){failed=true;throw error;}
  }
  public synchronized Map<String,Object> report(){
    var r=new LinkedHashMap<String,Object>();r.put("scope","INDEXED_ORIGINAL_DEVELOPMENT_EXECUTION_NOT_QUALIFICATION");
    r.put("sourceIndex",index.report());r.put("realReceiptPool",pool.report());r.put("lastAttemptedOriginalObservation",last);r.put("failed",failed);
    r.put("knownAppliedObservations",knownApplied);r.put("knownExpiredObservations",knownExpired);r.put("knownExpiredComponentQuantityNotApplied",expiredKnownQuantity);
    r.put("unknownAtomicClockObservations",unknownClock);r.put("unknownExpiredAtomicClockObservations",unknownExpired);
    r.put("unknownObservedPublicSizeNotVenueQuantity",observedUnknownPublicSize);r.put("unknownVenueQuantity","UNKNOWN_NOT_ZERO");
    r.put("venueConservationScope","KNOWN_NONEXPIRED_COMPONENTS_ONLY_NOT_COMPLETE_VENUE_VOLUME");
    r.put("aggregateFallbackAllowed",false);r.put("independentPaperQualificationAllowed",false);r.put("liveAllowed",false);return r;
  }
}
