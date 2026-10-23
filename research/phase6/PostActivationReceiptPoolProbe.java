package com.polybot.hft.paper;
import com.fasterxml.jackson.databind.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Exact645 original identities/1534 receipt components; identity parity only, never an account replay. */
public final class PostActivationReceiptPoolProbe {
  public static void main(String[] args)throws Exception {
    if(args.length!=3)throw new IllegalArgumentException("pool source-identities output");
    var m=NativeReplaySupport.M;Path pool=Path.of(args[0]),identities=Path.of(args[1]),out=Path.of(args[2]);
    if(Files.size(pool)>16000000||Files.size(identities)>16000000)throw new IllegalArgumentException("Bounded645 inputs required");
    var root=m.readTree(Files.readString(pool));var source=m.readTree(Files.readString(identities));
    if(!source.path("scope").asText().equals("EXACT645_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE")
        ||source.path("observations").size()!=645||root.path("expectedComponentCount").asInt()!=1534)
      throw new IllegalArgumentException("Complete645 source required");
    var labels=new ConservedReceiptPool(root,m);var hash=MessageDigest.getInstance("SHA-256");int consumed=0;
    for(var row:source.path("observations")) {
      long seq=row.path("seq").asLong();int index=row.path("eventIndex").asInt();
      var b=labels.resolve(seq,index,row.path("at").asLong(),row.path("data"));consumed++;
      for(var p:b.portions())hash.update((seq+"|"+index+"|"+p.identity()+"|"+p.token()+"|"+(p.buy()?"BUY":"SELL")+"|"+p.price().toPlainString()+"|"+p.quantity().toPlainString()+"\n").getBytes(StandardCharsets.UTF_8));
    }
    labels.requireConsumed();String actual=HexFormat.of().formatHex(hash.digest());
    if(!actual.equals(root.path("portionsLogicalSha256").asText()))throw new AssertionError("Native645 integer tuples differ");
    ConservedReceiptPoolProbe.selfTests();
    Files.createDirectory(out);var synthetic=ConservedReceiptPoolProbe.sessionGuard(out.resolve("synthetic-session"));
    if(ConservedReceiptPoolProbe.guards!=39)throw new AssertionError("Strict reader guards differ");
    var report=new LinkedHashMap<String,Object>();
    report.put("scope","ALL645_NATIVE_IDENTITY_PARITY_NOT_ACCOUNT_REPLAY");report.put("readerRejectionGuards",39);report.put("conservativeRoundingBoundaryCases",2);
    report.put("separateSyntheticUnknownGuard",synthetic);
    report.put("originalIdentities",consumed);report.put("pool",labels.report());report.put("portionsLogicalSha256",actual);
    report.put("poolLogicalSha256",ConservedReceiptPool.hash(Files.readString(pool)));report.put("sourceIdentitiesSha256",ConservedReceiptPool.hash(Files.readString(identities)));
    for(String k:List.of("marketNetPnlRecomputed","completeAccountComparisonPerformed","independentPaperQualificationAllowed","liveAllowed"))report.put(k,false);
    Files.writeString(out.resolve("native-proof.json"),m.writerWithDefaultPrettyPrinter().writeValueAsString(report)+"\n");
    System.out.println("ALL645 original identities and1534 conservative component tuples match Python; no account replay");
  }
}
