package com.polybot.hft.executor.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.polybot.hft.executor.sim.PaperExchangeSimulator;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/research/v1")
@ConditionalOnProperty(name = "paper.phase3.enabled", havingValue = "true")
@RequiredArgsConstructor
public class ResearchSnapshotController {
  private final PaperExchangeSimulator simulator;

  @Value("${polybot.executor-token:}")
  private String token;

  @PostConstruct
  void validate() {
    if (token.isBlank() || token.length() < 24)
      throw new IllegalStateException(
          "Research API requires an executor token of at least 24 characters");
  }

  @GetMapping("/snapshot")
  public ResponseEntity<JsonNode> snapshot() {
    try {
      return ResponseEntity.ok()
          .cacheControl(CacheControl.noStore())
          .body(simulator.researchSnapshot());
    } catch (IllegalStateException e) {
      throw new ResponseStatusException(
          HttpStatus.SERVICE_UNAVAILABLE, "Closed-loop PAPER snapshot unavailable");
    }
  }
}
