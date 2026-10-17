package com.polybot.hft.paper;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ResearchProposalInboxTest {
  @TempDir Path dir;
  final ObjectMapper mapper = new ObjectMapper();

  ObjectNode snapshot() throws Exception {
    return (ObjectNode)
        mapper.readTree(
            """
{"mode":"PAPER","liveAllowed":false,"executionEnabled":false,"truncated":false,"sessionId":"s","sequence":1,"generatedMs":1000,"maxBookAgeMs":2000,"metadataMaxAgeMs":60000,
 "account":{"id":"a","cash":"500","availableCash":"500","halted":false,"pendingTakers":0,"holdings":{},"orders":{}},
 "markets":[{"condition":"m","first":"x","second":"y","accepting":true,"startMs":0,"endMs":10000,"observedMs":1000,"minSize":"5","tick":"0.01"}],
 "books":{"x":{"sourceMs":1000,"depthTruncated":false,"bids":[{"price":"0.4"}],"asks":[{"price":"0.6"}]},"y":{"sourceMs":1000,"depthTruncated":false,"bids":[{"price":"0.4"}],"asks":[{"price":"0.6"}]}}}
""");
  }

  ObjectNode proposal() throws Exception {
    return (ObjectNode)
        mapper.readTree(
            """
{"id":"one","strategy":"test","sessionId":"s","accountId":"a","sequence":1,
 "legs":[{"condition":"m","token":"x","buy":true,"price":"0.41","size":"5","expiresMs":1100}]}
""");
  }

  @Test
  void durableIdempotencyAndNoAccountMutation() throws Exception {
    var before = snapshot();
    var copy = before.deepCopy();
    var request = proposal();
    JsonNode result;
    try (var inbox = new ResearchProposalInbox(mapper, dir.resolve("inbox.json"))) {
      result = inbox.screen(before, request);
      assertThat(result.path("executionEnabled").asBoolean()).isFalse();
      assertThat(before).isEqualTo(copy);
      assertThat(inbox.screen(before, request)).isEqualTo(result);
      request.put("strategy", "changed");
      assertThatThrownBy(() -> inbox.screen(before, request))
          .isInstanceOf(IllegalStateException.class);
    }
    try (var restored = new ResearchProposalInbox(mapper, dir.resolve("inbox.json"))) {
      assertThat(restored.screen(before, proposal())).isEqualTo(result);
      var second = proposal();
      second.put("id", "two");
      assertThatThrownBy(() -> restored.screen(before, second))
          .isInstanceOf(IllegalStateException.class);
    }
  }

  @Test
  void recoveryReadsDurableReceiptAfterSequenceChangeWithoutRescreening() throws Exception {
    var first = snapshot();
    var request = proposal();
    JsonNode receipt;
    try (var inbox = new ResearchProposalInbox(mapper, dir.resolve("recovery.json"))) {
      receipt = inbox.screen(first, request);
      var newer = first.deepCopy();
      newer.put("sequence", 2);
      assertThat(inbox.recordedScreenReceipt(newer, "one")).contains(receipt);
      assertThat(inbox.recordedScreenReceipt(newer, "unknown")).isEmpty();
      assertThat(first).isEqualTo(snapshot());
    }
    try (var restored = new ResearchProposalInbox(mapper, dir.resolve("recovery.json"))) {
      var newer = first.deepCopy();
      newer.put("sequence", 3);
      assertThat(restored.recordedScreenReceipt(newer, "one")).contains(receipt);
      ((ObjectNode) newer.path("account")).put("id", "other");
      assertThatThrownBy(() -> restored.recordedScreenReceipt(newer, "one"))
          .isInstanceOf(IllegalStateException.class);
      ((ObjectNode) newer.path("account")).put("id", "a");
      newer.put("sessionId", "another-session");
      assertThatThrownBy(() -> restored.recordedScreenReceipt(newer, "one"))
          .isInstanceOf(IllegalStateException.class);
    }
  }

  @Test
  void invalidShortStaleAndAtomicBudgetFailClosed() throws Exception {
    try (var inbox = new ResearchProposalInbox(mapper, dir.resolve("inbox.json"))) {
      var snapshot = snapshot();
      var proposal = proposal();
      proposal.put("sequence", 0);
      assertThatThrownBy(() -> inbox.screen(snapshot, proposal))
          .isInstanceOf(IllegalStateException.class);
      proposal.put("sequence", 1);
      ((ObjectNode) proposal.path("legs").get(0)).put("buy", false);
      assertThatThrownBy(() -> inbox.screen(snapshot, proposal))
          .isInstanceOf(IllegalStateException.class);
      ((ObjectNode) proposal.path("legs").get(0)).put("buy", true);
      ((ObjectNode) snapshot.path("account")).put("availableCash", "1");
      assertThatThrownBy(() -> inbox.screen(snapshot, proposal))
          .isInstanceOf(IllegalStateException.class);
      ((ObjectNode) snapshot.path("account")).put("availableCash", "500");
      assertThat(inbox.screen(snapshot, proposal).path("status").asText())
          .isEqualTo("SCREENED_SHADOW_ONLY");
    }
  }
}
