package com.polybot.hft.paper;

import java.nio.file.*;
import java.util.*;

/** Explicit isolated development CLI; no live/service registration or source filtering. */
public final class IndexedReplaySupport {
  public static void main(String[] args)throws Exception {
    if(args.length!=6||!Set.of("baseline","candidate").contains(args[5]))throw new IllegalArgumentException("original-tape new-output config pool complete-index baseline|candidate");
    if(!ClosedLoopReplay.sha256(Path.of(args[0])).equals("9363443ae9287016ab7c63d3cf11d6b1ae33d814d9e3ad340bb99b33e7285074")
        ||!ClosedLoopReplay.sha256(Path.of(args[2])).equals("a84b6b3283e15b0069aafe615d19abeebda8f3e4104467ed1111983ab5ddbc00"))throw new IllegalArgumentException("Frozen original development source/config required");
    var mapper=NativeReplaySupport.M;
    var cfg=mapper.readValue(Files.readString(Path.of(args[2])),ResearchConfig.class);
    var labels=new IndexedExecutionLabels(Path.of(args[3]),Path.of(args[4]),mapper);
    IndexedOriginalTapeReplay.runPartial(Path.of(args[0]),Path.of(args[1]),cfg,NativeReplaySupport.limits(),mapper,labels,args[5].equals("candidate"));
  }
}
