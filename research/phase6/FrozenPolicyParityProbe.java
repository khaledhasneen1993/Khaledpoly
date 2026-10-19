package com.polybot.hft.paper;
import com.fasterxml.jackson.databind.*;
import java.nio.file.*;
import java.util.*;

/** Pure rule parity only; never execution. */
public final class FrozenPolicyParityProbe {
  public static void main(String[] args)throws Exception {
    if(args.length!=2)throw new IllegalArgumentException("cases.json result.json");
    var m=new ObjectMapper().findAndRegisterModules();var input=m.readTree(Files.readString(Path.of(args[0])));
    var quotes=new ArrayList<Object>();var exits=new ArrayList<Object>();
    for(var c:input.path("quotes"))quotes.add(FrozenResearchPolicies.propose(c.path("witness"),m.treeToValue(c.path("config"),ResearchConfig.class)));
    for(var c:input.path("exits"))exits.add(FrozenResearchPolicies.choose(FrozenResearchPolicies.d(c.path("basis")),FrozenResearchPolicies.d(c.path("ask")),
        FrozenResearchPolicies.d(c.path("bid")),FrozenResearchPolicies.d(c.path("buyFee")),FrozenResearchPolicies.d(c.path("sellFee")),FrozenResearchPolicies.d(c.path("minimum")),c.path("overdue").asBoolean()));
    Files.writeString(Path.of(args[1]),m.writerWithDefaultPrettyPrinter().writeValueAsString(Map.of("quotes",quotes,"exits",exits,"scope","FROZEN_RULE_PARITY_NOT_ACCOUNT"))+"\n");
  }
}
