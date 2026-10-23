package com.polybot.hft.paper;

import java.util.*;

/** Bounded offline diagnostic selection, never a strategy input or service option. */
final class EntryDecisionWitness {
  record Window(String condition, long startMs, long endMs) {}
  final List<Window> windows;
  final List<Map<String,Object>> rows = new ArrayList<>();

  EntryDecisionWitness(List<Window> windows) {
    if (windows == null || windows.isEmpty() || windows.size()>20)
      throw new IllegalArgumentException("Require 1..20 bounded witness windows");
    long total=0;
    for (var w:windows) {
      if (w==null || w.condition()==null || !w.condition().matches("0x[0-9a-f]{64}")
          || w.startMs()<0 || w.endMs()<w.startMs() || w.endMs()-w.startMs()>3000)
        throw new IllegalArgumentException("Invalid bounded decision window");
      total+=w.endMs()-w.startMs();
    }
    if (total>30000) throw new IllegalArgumentException("Witness duration cap exceeded");
    this.windows=List.copyOf(windows);
  }

  boolean selects(String condition,long at) {
    return windows.stream().anyMatch(w->w.condition().equals(condition) && w.startMs()<=at && at<=w.endMs());
  }

  void append(Map<String,Object> row) {
    if (rows.size()>=500) throw new IllegalStateException("Witness cap exceeded; never silently truncate");
    rows.add(Collections.unmodifiableMap(new LinkedHashMap<>(row)));
  }
}
