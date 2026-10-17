package com.polybot.hft.executor.web;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.executor.sim.PaperExchangeSimulator;
import com.polybot.hft.paper.ResearchProposalInbox;
import jakarta.annotation.PreDestroy;
import java.nio.file.Path;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/research/v1/proposals")
@ConditionalOnProperty(name = "paper.phase3.enabled", havingValue = "true")
public class ResearchProposalController {
  private final PaperExchangeSimulator simulator;
  private final ResearchProposalInbox inbox;

  public ResearchProposalController(
      PaperExchangeSimulator simulator,
      ObjectMapper mapper,
      @Value("${executor.account.state-path:state/paper-account.json}") String statePath) {
    this.simulator = simulator;
    inbox = new ResearchProposalInbox(mapper, Path.of(statePath + ".proposals"));
  }

  @PostMapping("/screen")
  public ResponseEntity<JsonNode> screen(@RequestBody JsonNode proposal) {
    if (proposal.toString().length() > 65536)
      throw new ResponseStatusException(HttpStatus.PAYLOAD_TOO_LARGE);
    JsonNode snapshot;
    try {
      snapshot = simulator.researchSnapshot();
    } catch (IllegalStateException e) {
      throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "PAPER unavailable");
    }
    try {
      return ResponseEntity.ok()
          .cacheControl(CacheControl.noStore())
          .body(inbox.screen(snapshot, proposal));
    } catch (IllegalArgumentException e) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage());
    } catch (IllegalStateException e) {
      throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
    }
  }

  @GetMapping("/screen-receipts/{id}")
  public ResponseEntity<JsonNode> savedScreenReceipt(@PathVariable String id) {
    JsonNode snapshot;
    try {
      snapshot = simulator.researchSnapshot();
    } catch (IllegalStateException e) {
      throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "PAPER unavailable");
    }
    try {
      return inbox.recordedScreenReceipt(snapshot, id)
          .map(receipt -> ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(receipt))
          .orElseGet(() -> ResponseEntity.notFound().cacheControl(CacheControl.noStore()).build());
    } catch (IllegalArgumentException e) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage());
    } catch (IllegalStateException e) {
      throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
    }
  }

  @PostMapping("/paper")
  public ResponseEntity<JsonNode> paper(@RequestBody JsonNode proposal) {
    try {
      var receipt = simulator.submitPaperProposal(proposal);
      return ResponseEntity.status(
              receipt.path("status").asText().equals("PAPER_REJECTED") ? 409 : 200)
          .cacheControl(CacheControl.noStore())
          .body(receipt);
    } catch (IllegalStateException e) {
      throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
    }
  }

  @PostMapping("/settle-paper-group")
  public ResponseEntity<JsonNode> settleGroup(@RequestBody JsonNode request) {
    try {
      return ResponseEntity.ok()
          .cacheControl(CacheControl.noStore())
          .body(simulator.settlePaperGroup(request.path("eventId").asText()));
    } catch (IllegalArgumentException e) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage());
    } catch (IllegalStateException e) {
      throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
    }
  }

  @PreDestroy
  void close() {
    inbox.close();
  }
}
