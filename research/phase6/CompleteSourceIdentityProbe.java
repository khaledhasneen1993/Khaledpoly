package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Original identities only; this probe never creates an order/session/fill. */
public final class CompleteSourceIdentityProbe {
  private static final ObjectMapper M=new ObjectMapper();
  private static void check(boolean condition,String why){if(!condition)throw new AssertionError(why);}
  private static void rejects(Runnable task){try{task.run();}catch(IllegalArgumentException|IllegalStateException expected){return;}throw new AssertionError("Unsafe input accepted");}
  private static CompleteSourceIdentityIndex subset(Path path)throws Exception{return new CompleteSourceIdentityIndex(path,CompleteSourceIdentityIndex.Mode.RETAINED_PREIMAGE_SUBSET_ONLY);}
  private static void consume(CompleteSourceIdentityIndex reader,JsonNode n){reader.consume(n.path("seq").asLong(),n.path("eventIndex").asInt(),n.path("at").asLong(),n.path("data"));}

  public static void main(String[] args)throws Exception {
    if(args.length!=3)throw new IllegalArgumentException("index, original identities, new output required");
    Path index=Path.of(args[0]),inputs=Path.of(args[1]),output=Path.of(args[2]);
    byte[] raw=Files.readAllBytes(inputs);
    check(raw.length<4*1024*1024,"Bounded identities");JsonNode source=M.readTree(raw);
    check(source.path("scope").asText().equals("EXACT643_ORIGINAL_IDENTITY_INPUTS_NOT_EXECUTION_TAPE"),"Original preimage scope");
    check(CompleteSourceIdentityIndex.sha(raw).equals("27ac545988149c87bdfd4caee963100b7d10eb2808e6a74d82ae4b8321c65423"),"Frozen ALL643 original preimages");
    var actual=source.path("observations");check(actual.isArray()&&actual.size()==643,"All643 required");
    var reader=subset(index);
    for(var n:actual)consume(reader,n);
    check(reader.report().get("consumedOriginalPreimages").equals(643),"Incomplete original parity");
    Map<String,Object> before=reader.report();rejects(reader::requireComplete);
    check(reader.report().get("failed").equals(true),"Finalization must poison");rejects(()->consume(reader,actual.get(0)));
    var guards=new ArrayList<String>();guards.add("SUBSET_CANNOT_CERTIFY_COMPLETE");guards.add("FAILED_FINALIZATION_NO_CONTINUATION");
    Map<String,Consumer<ObjectNode>> changes=new LinkedHashMap<>();
    changes.put("WRONG_SEQUENCE",n->n.put("seq",0));changes.put("WRONG_FRAME_INDEX",n->n.put("eventIndex",99999));
    changes.put("WRONG_ARRIVAL",n->n.put("at",0));changes.put("WRONG_SOURCE",n->((ObjectNode)n.path("data")).put("sourceMs",0));
    changes.put("WRONG_TOKEN",n->((ObjectNode)n.path("data")).put("token","1"));
    changes.put("WRONG_SIDE",n->((ObjectNode)n.path("data")).put("side","INVALID"));
    changes.put("WRONG_PRICE",n->((ObjectNode)n.path("data")).put("price","0.12345"));
    changes.put("WRONG_SIZE",n->((ObjectNode)n.path("data")).put("size","99999"));
    changes.put("PRICE_NAN",n->((ObjectNode)n.path("data")).put("price","NaN"));
    changes.put("SIZE_BOOLEAN",n->((ObjectNode)n.path("data")).put("size",true));
    changes.put("SOURCE_BOOLEAN",n->((ObjectNode)n.path("data")).put("sourceMs",true));
    changes.put("SOURCE_FRACTIONAL",n->((ObjectNode)n.path("data")).put("sourceMs",0.5));
    changes.put("RAW_BYTES_WHITESPACE",n->((ObjectNode)n.path("data")).put("tradeId",n.path("data").path("tradeId").asText()+" "));
    changes.put("RAW_TRANSACTION_MUTATION",n->((ObjectNode)n.path("data")).put("tradeId","{\"transaction_hash\":\"0x"+"0".repeat(64)+"\"}"));
    changes.put("RAW_MISSING",n->((ObjectNode)n.path("data")).remove("tradeId"));
    changes.put("RAW_OVERSIZED",n->((ObjectNode)n.path("data")).put("tradeId","x".repeat(1024*1024+1)));
    for(var entry:changes.entrySet()) {
      var test=subset(index);ObjectNode changed=actual.get(0).deepCopy();entry.getValue().accept(changed);
      rejects(()->consume(test,changed));check(test.report().get("failed").equals(true),"Unpoisoned "+entry.getKey());
      rejects(()->consume(test,actual.get(0)));guards.add(entry.getKey());
    }
    var duplicate=subset(index);consume(duplicate,actual.get(0));rejects(()->consume(duplicate,actual.get(0)));
    check(duplicate.report().get("failed").equals(true),"Duplicate not poisoned");guards.add("DUPLICATE_CONSUMPTION");
    var reverse=subset(index);consume(reverse,actual.get(1));rejects(()->consume(reverse,actual.get(0)));
    check(reverse.report().get("failed").equals(true),"Reverse not poisoned");guards.add("REVERSED_CONSUMPTION");
    var full=new CompleteSourceIdentityIndex(index);consume(full,actual.get(0));
    check(full.report().get("consumedOriginalPreimages").equals(1),"First original97 required");
    // Next original is628, not the next retained receipt-pool preimage.
    rejects(()->consume(full,actual.get(1)));check(full.report().get("failed").equals(true),"Missing not poisoned");guards.add("FULL_MODE_NO_MISSING_OBSERVATION");
    var unfinished=new CompleteSourceIdentityIndex(index);rejects(unfinished::requireComplete);
    check(unfinished.report().get("failed").equals(true),"Incomplete not poisoned");guards.add("EMPTY_CANNOT_CERTIFY_COMPLETE");
    check(!Files.exists(output),"Do not overwrite evidence");Files.createDirectories(output);
    Path changedIndex=output.resolve("tampered-index.tmp");byte[] bytes=Files.readAllBytes(index);bytes[0]=' ';
    Files.write(changedIndex,bytes);
    try{new CompleteSourceIdentityIndex(changedIndex);throw new AssertionError("Changed index accepted");}
    catch(IllegalArgumentException expected){guards.add("CHANGED_FULL_CENSUS_BYTES");}finally{Files.delete(changedIndex);}
    Map<String,Object> proof=new LinkedHashMap<>();proof.put("scope","NATIVE_COMPLETE_INDEX_WITH643_PREIMAGE_PARITY_NOT_EXECUTION");
    proof.put("indexLogicalSha256",CompleteSourceIdentityIndex.INDEX_SHA);proof.put("sourceIdentitiesSha256",CompleteSourceIdentityIndex.sha(raw));
    proof.put("originalIdentities",16317);proof.put("actualRawPreimagesMatched",643);proof.put("unconsumedOriginalPreimages",15674);
    proof.put("preimageSubsetBeforeRejectedFinalization",before);proof.put("rejectionGuards",guards);proof.put("allRejectionsPoisonConsumption",true);
    proof.put("fullModeFirstOriginal97Matched",true);proof.put("fullModeMissing628Rejected",true);
    for(String flag:List.of("runtimeOptimizationImplemented","atomicSessionGuardImplemented","originalTapeReplayed","modelFillsCreated",
        "marketNetPnlRecomputed","fullAccountReplayAuthorized","independentPaperQualificationAllowed","liveAllowed"))proof.put(flag,false);
    M.writerWithDefaultPrettyPrinter().writeValue(output.resolve("native-index-proof.json").toFile(),proof);
    System.out.println(M.writeValueAsString(proof));
  }
}
