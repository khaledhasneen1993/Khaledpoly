package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.*;
import java.util.*;

/** Exact causal QW0 admission/queue objective and frozen fee-positive choice; offline profile only. */
final class FrozenResearchPolicies {
  record Level(BigDecimal price,int index,BigDecimal size) {}
  record Quote(BigDecimal firstBid,BigDecimal secondBid,BigDecimal quantity,BigDecimal requiredEdge,
      BigDecimal originalRequiredEdge,BigDecimal thinPremiumReserve,int firstLevelIndex,int secondLevelIndex,
      BigDecimal firstDisplayedSize,BigDecimal secondDisplayedSize,BigDecimal firstDisplayedQueueProxy,
      BigDecimal secondDisplayedQueueProxy,BigDecimal netEdgeTotal,BigDecimal worstUnpairedLoss,boolean queuePriorityOrFillProven) {}
  static BigDecimal d(JsonNode n){return new BigDecimal(n.asText());}
  static Quote propose(JsonNode w,ResearchConfig cfg) {
    if(!w.hasNonNull("quantity")||!w.hasNonNull("requiredEdge"))return null;
    var m=w.path("market");long at=w.path("at").asLong();BigDecimal q=d(w.path("quantity"));
    if(w.path("entryStopped").asBoolean()||w.path("ledgerHalted").asBoolean()||w.path("resolved").asBoolean()
        ||!w.path("openOrderIds").isEmpty()||d(w.path("imbalance")).signum()!=0||!m.path("accepting").asBoolean()
        ||at<m.path("startMs").asLong()||at>=m.path("endMs").asLong()||at-m.path("observedMs").asLong()>cfg.metadataMaxAgeMs()
        ||q.compareTo(d(m.path("minSize")))<0)return null;
    JsonNode a=w.path("firstBook"),b=w.path("secondBook");
    for(var book:List.of(a,b))if(book.isNull()||book.path("bids").isEmpty()||book.path("asks").isEmpty()
        ||at<book.path("sourceMs").asLong()||at-book.path("sourceMs").asLong()>cfg.maxBookAgeMs())return null;
    BigDecimal depth=d(a.path("bids").get(0).path("size")).min(d(b.path("bids").get(0).path("size")));
    if(q.compareTo(cfg.orderShares().min(depth.multiply(new BigDecimal(".1"))).setScale(2,RoundingMode.DOWN))!=0)
      throw new IllegalArgumentException("Do not increase original causal top-depth quantity");
    for(int i=0;i<2;i++) {
      var last=w.path(i==0?"lastFirstTakerSource":"lastSecondTakerSource");var book=i==0?a:b;
      if(!last.isNull()&&!last.isMissingNode()&&book.path("sourceMs").asLong()<=last.asLong())return null;
    }
    if(cfg.queueMultiplier().compareTo(BigDecimal.ONE)<0)throw new IllegalArgumentException("Do not relax queue model");
    BigDecimal tick=d(m.path("tick")),thin=BigDecimal.ONE.divide(depth.max(BigDecimal.ONE),8,RoundingMode.CEILING).min(new BigDecimal(".02"));
    BigDecimal reserve=new BigDecimal(".02").subtract(thin),original=d(w.path("requiredEdge")),required=original.add(reserve);
    var candidates=new ArrayList<Quote>();
    for(var first:levels(a,tick,q))for(var second:levels(b,tick,q)) {
      BigDecimal net=BigDecimal.ONE.subtract(first.price()).subtract(second.price()).multiply(q).subtract(cfg.mergeCost());
      BigDecimal cost=first.price().add(second.price()).multiply(q),loss=q.multiply(first.price().max(second.price())).add(cfg.redemptionCost());
      if(net.compareTo(required.multiply(q))<0||loss.compareTo(d(w.path("exitLossAvailable")))>0
          ||cost.compareTo(d(w.path("availableCash")))>0||d(w.path("gross")).add(cost).compareTo(cfg.portfolioBudget())>0)continue;
      candidates.add(new Quote(first.price(),second.price(),q,required,original,reserve,first.index(),second.index(),first.size(),second.size(),
          first.size().multiply(cfg.queueMultiplier()),second.size().multiply(cfg.queueMultiplier()),net,loss,false));
    }
    // reserve>=0, so every admitted QW0 candidate also passes the frozen DQ3 existence gate.
    return candidates.stream().min(Comparator.comparing((Quote r)->r.firstDisplayedQueueProxy().max(r.secondDisplayedQueueProxy()))
        .thenComparing(r->r.firstDisplayedQueueProxy().add(r.secondDisplayedQueueProxy()))
        .thenComparing(r->r.firstBid().add(r.secondBid()).negate())
        .thenComparingInt(r->Math.max(r.firstLevelIndex(),r.secondLevelIndex()))
        .thenComparingInt(r->r.firstLevelIndex()+r.secondLevelIndex()).thenComparing(r->r.firstBid().negate())).orElse(null);
  }
  private static List<Level> levels(JsonNode b,BigDecimal tick,BigDecimal q) {
    var result=new ArrayList<Level>();int i=0;
    for(var n:b.path("bids")) {
      if(i>=3)break;BigDecimal p=d(n.path("price")),size=d(n.path("size"));
      if(p.compareTo(tick)>=0&&p.compareTo(BigDecimal.ONE.subtract(tick))<=0&&p.remainder(tick).signum()==0
          &&p.compareTo(d(b.path("asks").get(0).path("price")))<0&&size.compareTo(q.multiply(BigDecimal.TEN))>=0)result.add(new Level(p,i,size));
      i++;
    }
    return result;
  }
  static PairPolicy.HedgeChoice choose(BigDecimal basis,BigDecimal ask,BigDecimal bid,BigDecimal buyFee,BigDecimal sellFee,BigDecimal minimum,boolean overdue) {
    var old=PairPolicy.hedge(basis,ask,bid,buyFee,sellFee,minimum,overdue);
    if(!overdue&&old.completeValue().max(old.sellValue()).compareTo(minimum)>=0)
      return new PairPolicy.HedgeChoice(old.completeValue().compareTo(old.sellValue())>=0?"COMPLETE":"TAKER_SELL",old.completeValue(),old.sellValue());
    return old;
  }
}
