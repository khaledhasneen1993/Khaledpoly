import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.polybot.hft.paper.PaperMatchingEngine;
import java.math.BigDecimal;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Uses the immutable already-built matcher; NEVER simulates trades, fills or account profit. */
public final class Dq3ActivationProbe {
  static final ObjectMapper M=new ObjectMapper();
  static final JsonNode EMPTY=M.createObjectNode();
  static JsonNode n(Object x) { return M.valueToTree(x); }
  static void feed(PaperMatchingEngine e,String kind,long at,JsonNode d,Set<String> pair) {
    if (kind.equals("GAP")) {
      var affected=new HashSet<String>();d.path("tokens").forEach(t->affected.add(t.asText()));
      if(d.has("token"))affected.add(d.path("token").asText());
      if(affected.isEmpty()||affected.stream().anyMatch(pair::contains))
        e.accept("GAP",at,n(Map.of("tokens",pair,"reason",d.path("reason").asText("unknown"))));
      // Unrelated GAP also returns before activation in the real matcher.
      else e.accept("GAP",at,d);
    } else if (kind.equals("BOOK")) e.accept("BOOK",at,d);
    else if (kind.equals("TRADE")||kind.equals("TICK")) {
      // Only trigger the identical pre-event activation path. Never allocate public print volume.
      var update=e.accept("TICK",at,EMPTY);
      if(!update.fills().isEmpty())throw new IllegalStateException("Probe cannot emit fills");
    }
  }
  static void selfTest() {
    var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));
    var old=n(Map.of("token","a","sourceMs",900,"bids",List.of(Map.of("price","0.49","size","840")),
        "asks",List.of(Map.of("price","0.51","size","100"))));
    e.accept("BOOK",900,old);
    e.accept("ORDER",1000,n(Map.of("id","test","token","a","side","BUY","price","0.49","size","5")));
    var newer=n(Map.of("token","a","sourceMs",1250,"bids",List.of(Map.of("price","0.49","size","1")),
        "asks",List.of(Map.of("price","0.51","size","100"))));
    e.accept("BOOK",1251,newer);var d=e.diagnostics().getFirst();
    if(!d.get("initialQueueAhead").equals(new BigDecimal("1680"))||!d.get("activatedMs").equals(1251L))
      throw new AssertionError("Activation must seed PRE-event book, not decision or new book");
    var gap=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));
    gap.accept("BOOK",900,old);gap.accept("ORDER",1000,n(Map.of("id","gap","token","a","side","BUY","price","0.49","size","5")));
    feed(gap,"GAP",1251,n(Map.of("token","b","reason","invalid_depth")),Set.of("a","b"));
    if(gap.diagnostics().getFirst().get("activatedMs")!=null)throw new AssertionError("GAP must win activation");
    System.out.println("2 actual-matcher activation assertions passed");
  }
  public static void main(String[] args)throws Exception {
    if(args.length==1&&args[0].equals("--self-test")){selfTest();return;}
    if(args.length!=2)throw new IllegalArgumentException("context.json.gz output.json");
    JsonNode context;
    try(var in=new GZIPInputStream(Files.newInputStream(Path.of(args[0])))){context=M.readTree(in);}
    var results=new ArrayList<Object>();
    for(var state:context.path("spec").path("states")) {
      var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));
      var pair=new HashSet<String>();state.path("quotes").forEach(q->pair.add(q.path("token").asText()));
      long anchor=state.path("originalSequence").asLong(),due=state.path("activationDueMs").asLong();
      boolean submitted=false,tickChange=false;Long firstDueSeq=null,observedSeq=null;Integer observedEvent=null;
      var diag=new LinkedHashMap<String,Object>();
      for(var record:context.path("records")) {
        var row=record.path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();
        String kind=row.path("kind").asText().substring(9);var data=row.path("data");
        if(submitted&&at>=due&&firstDueSeq==null)firstDueSeq=seq;
        var events=kind.equals("FRAME")?data.path("events"):n(List.of(Map.of("kind",kind,"data",data)));
        int index=0;
        for(var event:events) {
          String k=event.path("kind").asText();var d=event.path("data");
          if(submitted&&k.equals("TICK_SIZE"))tickChange=true;
          if(k.equals("FEED_ERROR"))k="GAP";
          feed(e,k,at,d,pair);
          if(submitted&&!e.diagnostics().isEmpty()) {
            var current=e.diagnostics().getFirst();
            if(current.get("activatedMs")!=null||current.get("terminalMs")!=null) {
              diag.putAll(current);observedSeq=seq;observedEvent=index;break;
            }
          }
          index++;
        }
        if(observedSeq!=null)break;
        if(seq==anchor) {
          var quote=state.path("targetQuote");
          e.accept("ORDER",at,n(Map.of("id","dq3-seed-"+anchor,"token",quote.path("token").asText(),
              "side","BUY","price",quote.path("price").asText(),"size",quote.path("quantity").asText())));
          submitted=true;
        }
      }
      if(!submitted||observedSeq==null)throw new IllegalStateException("Missing source anchor/activation outcome");
      var result=new LinkedHashMap<String,Object>();
      result.put("state",state);result.put("diagnostic",diag);result.put("firstInputAtOrAfterDueSequence",firstDueSeq);
      result.put("activationOutcomeSequence",observedSeq);result.put("activationOutcomeEventIndex",observedEvent);
      result.put("sameFirstDueInput",Objects.equals(firstDueSeq,observedSeq));result.put("tickChangeSinceSubmission",tickChange);
      results.add(result);
    }
    Files.writeString(Path.of(args[1]),M.writerWithDefaultPrettyPrinter().writeValueAsString(Map.of(
        "scope","ISOLATED_NO_CANCEL_ACTIVATION_SEED_ONLY_NOT_ACTUAL_ACCOUNT",
        "results",results,"allTradeVolumeSuppressed",true,"fillsCreated",0,"netPnlRecomputed",false,
        "actualRestingCancellationSimulated",false,"independentPaperQualificationAllowed",false,"liveAllowed",false))+"\n");
  }
}
