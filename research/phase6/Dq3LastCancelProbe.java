import com.fasterxml.jackson.databind.*;
import com.polybot.hft.paper.PaperMatchingEngine;
import com.polybot.hft.paper.PairPolicy;
import java.math.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;

/** Conditional isolated pair risk check, NOT a strategy/account replay. */
public final class Dq3LastCancelProbe {
  static final ObjectMapper M=new ObjectMapper().enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS);
  static BigDecimal dec(JsonNode n){return n.isTextual()?new BigDecimal(n.asText()):n.decimalValue();}
  static JsonNode node(Object o){return M.valueToTree(o);}
  public static void main(String[] args)throws Exception {
    if(args.length!=3)throw new IllegalArgumentException("context.gz original-witness-report.json cancel-report.json");
    JsonNode context;
    try(var in=new GZIPInputStream(Files.newInputStream(Path.of(args[0])))){context=M.readTree(in);}
    var report=M.readTree(Files.readString(Path.of(args[1])));
    JsonNode witness=null;
    for(var w:report.path("entryDecisionWitnesses"))if(w.path("originalSequence").asLong()==299997)witness=w;
    if(witness==null)throw new IllegalStateException("Missing original risk witness");
    var state=context.path("spec").path("states").get(0);
    if(state.path("originalSequence").asLong()!=299650)throw new IllegalArgumentException("Wrong isolated start");
    var e=new PaperMatchingEngine(250,250,2000,new BigDecimal("2"));
    var pair=new HashSet<String>();state.path("quotes").forEach(q->pair.add(q.path("token").asText()));
    String target=state.path("targetQuote").path("token").asText();
    boolean submitted=false,canceled=false;Map<String,Object> terminal=null;long terminalSeq=-1;
    BigDecimal required=null,net=null,quantity=dec(state.path("targetQuote").path("quantity"));
    long requested=-1;
    for(var record:context.path("records")) {
      var row=record.path("input");long at=row.path("arrivalMs").asLong(),seq=row.path("seq").asLong();
      String kind=row.path("kind").asText().substring(9);var data=row.path("data");
      var events=kind.equals("FRAME")?data.path("events"):node(List.of(Map.of("kind",kind,"data",data)));
      for(var event:events) {
        String k=event.path("kind").asText();if(k.equals("FEED_ERROR"))k="GAP";
        Dq3ActivationProbe.feed(e,k,at,event.path("data"),pair);
      }
      if(seq==299650) {
        if(at!=state.path("submitMs").asLong())throw new IllegalStateException("Changed submit clock");
        for(var q:state.path("quotes"))e.accept("ORDER",at,node(Map.of("id","conditional-"+q.path("token").asText(),
            "token",q.path("token").asText(),"side","BUY","price",q.path("price").asText(),"size",quantity)));
        submitted=true;
      }
      if(seq==299997) {
        if(!submitted||at!=witness.path("at").asLong()||at!=state.path("activationDueMs").asLong())
          throw new IllegalStateException("Changed first scheduled risk callback");
        var a=witness.path("firstBook");var b=witness.path("secondBook");
        var depth=dec(a.path("bids").get(0).path("size")).min(dec(b.path("bids").get(0).path("size")));
        var vol=dec(witness.path("firstObservedVolatility")).max(dec(witness.path("secondObservedVolatility")));
        required=PairPolicy.requiredEdge(new BigDecimal(".01"),vol,witness.path("secondsToExpiry").asLong(),depth,250,BigDecimal.ZERO);
        if(required.compareTo(dec(witness.path("requiredEdge")))!=0)throw new AssertionError("Actual PairPolicy differs from original witness");
        var p=dec(state.path("quotes").get(0).path("price"));var q=dec(state.path("quotes").get(1).path("price"));
        net=BigDecimal.ONE.subtract(p).subtract(q).multiply(quantity).subtract(new BigDecimal(".01"));
        if(net.compareTo(required.multiply(quantity))>=0||p.compareTo(dec(a.path("asks").get(0).path("price")))>=0
            ||q.compareTo(dec(b.path("asks").get(0).path("price")))>=0)throw new AssertionError("No RESTING_NET_EDGE cancellation");
        for(var d:e.diagnostics()) {
          if(d.get("activatedMs")==null||d.get("terminalMs")!=null)throw new AssertionError("Pair must still be active before risk check");
          if(d.get("token").equals(target)&&new BigDecimal(d.get("initialQueueAhead").toString()).compareTo(new BigDecimal("200"))!=0)
            throw new AssertionError("Changed actual activation queue");
          e.accept("CANCEL",at,node(Map.of("id",d.get("id"),"reason","RESTING_NET_EDGE")));
        }
        requested=at;canceled=true;
      }
      if(canceled)for(var d:e.diagnostics())if(d.get("token").equals(target)&&d.get("terminalMs")!=null) {
        terminal=d;terminalSeq=seq;break;
      }
      if(terminal!=null)break;
    }
    if(terminal==null||!terminal.get("terminalReason").equals("RESTING_NET_EDGE"))throw new AssertionError("Missing actual engine cancel acknowledgement");
    var out=new LinkedHashMap<String,Object>();
    out.put("scope","CONDITIONAL_ISOLATED_PAIR_FIRST_RESTING_CHECK_NOT_ACTUAL_ACCOUNT");
    out.put("originalSequence",299650);out.put("cancelRequestSequence",299997);out.put("cancelRequestMs",requested);
    out.put("cancelDueMs",requested+250);out.put("cancelAckSequence",terminalSeq);out.put("targetDiagnostic",terminal);
    out.put("requiredEdge",required);out.put("reservedNetEdgeTotal",net);out.put("restingQuantity",quantity);
    out.put("legacyNewEntryQuantityNotUsed",witness.path("quantity"));
    out.put("allTradeVolumeSuppressed",true);out.put("fillsCreated",0);out.put("netPnlRecomputed",false);
    out.put("candidateAccountSimulated",false);out.put("independentPaperQualificationAllowed",false);out.put("liveAllowed",false);
    Files.writeString(Path.of(args[2]),M.writerWithDefaultPrettyPrinter().writeValueAsString(out)+"\n");
  }
}
