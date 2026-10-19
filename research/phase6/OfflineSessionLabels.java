package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Map;

/** Explicit offline-only source-built bridge; not included in the normal service build. */
interface OfflineSessionLabels {
  enum Profile { LEGACY, MIXED_BINDING_BRIDGE0 }
  SettlementReplayLabels.Binding resolve(long seq,int index,long at,JsonNode trade);
  Map<String,Object> report();
  void requireConsumed();
  Profile profile();

  static OfflineSessionLabels legacy(SettlementReplayLabels labels) {
    if(labels==null)return null;
    return new OfflineSessionLabels() {
      public SettlementReplayLabels.Binding resolve(long seq,int index,long at,JsonNode trade){return labels.resolve(seq,index,at,trade);}
      public Map<String,Object> report(){return labels.report();}
      public void requireConsumed(){labels.requireConsumed();}
      public Profile profile(){return Profile.LEGACY;}
    };
  }

  static OfflineSessionLabels mixed(ConservedMixedReplayLabels labels) {
    if(labels==null)throw new IllegalArgumentException("Mixed labels required");
    return new OfflineSessionLabels() {
      public SettlementReplayLabels.Binding resolve(long seq,int index,long at,JsonNode trade){return labels.resolve(seq,index,at,trade);}
      public Map<String,Object> report(){return labels.report();}
      public void requireConsumed(){labels.requireConsumed();}
      public Profile profile(){return Profile.MIXED_BINDING_BRIDGE0;}
    };
  }
}
