package com.polybot.hft.executor.sim;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Optional delivery adapters; unset endpoints leave a durable local outbox. Never log tokens/URLs.
 */
@Component
public class PaperAlertDispatcher {
  private final PaperExchangeSimulator simulator;
  private final ObjectMapper mapper;
  private final HttpClient http;
  private final Clock clock;

  @Value("${paper.alerts.slack-webhook:}")
  private String slack;

  @Value("${paper.alerts.telegram-token:}")
  private String telegram;

  @Value("${paper.alerts.telegram-chat:}")
  private String chat;

  public PaperAlertDispatcher(
      PaperExchangeSimulator simulator, ObjectMapper mapper, HttpClient http, Clock clock) {
    this.simulator = simulator;
    this.mapper = mapper;
    this.http = http;
    this.clock = clock;
  }

  @Scheduled(initialDelay = 10000, fixedDelay = 5000)
  public void dispatch() {
    if (slack.isBlank() && telegram.isBlank()) return;
    for (var alert : simulator.pendingAlerts(clock.millis())) {
      boolean success = true;
      try {
        if (!slack.isBlank()) {
          URI uri = URI.create(slack);
          if (!uri.getScheme().equals("https") || !uri.getHost().equals("hooks.slack.com"))
            throw new IllegalArgumentException("Invalid Slack endpoint");
          success &=
              send(
                  uri,
                  Map.of(
                      "text",
                      "Polybot PAPER ["
                          + (alert.key().startsWith("unhedged:") || alert.key().equals("risk-halt")
                              ? "CRITICAL"
                              : "WARNING")
                          + "] "
                          + alert.key()
                          + ": "
                          + alert.message()),
                  false);
        }
        if (!telegram.isBlank()) {
          if (chat.isBlank() || !telegram.matches("[0-9]+:[A-Za-z0-9_-]+"))
            throw new IllegalArgumentException("Invalid Telegram configuration");
          success &=
              send(
                  URI.create("https://api.telegram.org/bot" + telegram + "/sendMessage"),
                  Map.of(
                      "chat_id",
                      chat,
                      "text",
                      "Polybot PAPER ["
                          + (alert.key().startsWith("unhedged:") || alert.key().equals("risk-halt")
                              ? "CRITICAL"
                              : "WARNING")
                          + "] "
                          + alert.key()
                          + ": "
                          + alert.message()),
                  true);
        }
      } catch (Exception e) {
        success = false;
      }
      simulator.acknowledgeAlert(alert.key(), success, clock.millis());
    }
  }

  private boolean send(URI uri, Object body, boolean requireOk) throws Exception {
    var response =
        http.send(
            HttpRequest.newBuilder(uri)
                .timeout(Duration.ofSeconds(2))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body)))
                .build(),
            HttpResponse.BodyHandlers.ofString());
    return response.statusCode() == 200
        && (!requireOk || mapper.readTree(response.body()).path("ok").asBoolean(false));
  }
}
