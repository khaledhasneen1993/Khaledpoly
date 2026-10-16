package com.polybot.hft.executor.order;

import com.fasterxml.jackson.databind.*;
import com.polybot.hft.config.HftProperties;
import com.polybot.hft.polymarket.auth.PolymarketAuthContext;
import com.polybot.hft.polymarket.clob.PolymarketClobClient;
import jakarta.annotation.PreDestroy;
import java.net.URI;
import java.net.http.*;
import java.time.Clock;
import java.util.*;
import java.util.concurrent.*;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Authenticated order events trigger REST reconciliation; they never fabricate fills. */
@Component
@RequiredArgsConstructor
public class UserChannelService {
  public record OrderChanged(String orderId) {}

  private final HftProperties properties;
  private final PolymarketAuthContext auth;
  private final PolymarketClobClient clob;
  private final HttpClient http;
  private final ObjectMapper mapper;
  private final Clock clock;
  private final ApplicationEventPublisher events;
  private final ExecutorService reconciler = Executors.newSingleThreadExecutor();
  private volatile WebSocket socket;
  private volatile long lastReceived;
  private volatile long lastConnect;
  private volatile boolean stopped;
  private volatile boolean reconciled;
  private String heartbeatId = "";

  public boolean healthy() {
    return reconciled && socket != null && clock.millis() - lastReceived < 15000;
  }

  @Scheduled(initialDelay = 1000, fixedDelay = 5000)
  synchronized void maintain() {
    if (stopped
        || properties.mode() != HftProperties.TradingMode.LIVE
        || !properties.polymarket().userWsEnabled()) return;
    try {
      if (socket == null || !reconciled || clock.millis() - lastReceived > 15000) {
        if (clock.millis() - lastConnect < 10000) return;
        lastConnect = clock.millis();
        reconciled = false;
        if (socket != null) socket.abort();
        String base = properties.polymarket().clobWsUrl().replaceAll("/$", "");
        socket =
            http.newWebSocketBuilder()
                .buildAsync(URI.create(base + "/ws/user"), new Listener())
                .orTimeout(10, TimeUnit.SECONDS)
                .join();
        var credentials = auth.requireApiCreds();
        socket
            .sendText(
                mapper.writeValueAsString(
                    Map.of(
                        "type",
                        "user",
                        "markets",
                        properties.polymarket().userMarketIds(),
                        "auth",
                        Map.of(
                            "apiKey",
                            credentials.key(),
                            "secret",
                            credentials.secret(),
                            "passphrase",
                            credentials.passphrase()))),
                true)
            .orTimeout(5, TimeUnit.SECONDS)
            .join();
        // Reconcile before marking the connection usable. Open orders and trades stay
        // authoritative.
        clob.getOrders(auth.requireSignerCredentials(), credentials, Map.of());
        clob.getTrades(auth.requireSignerCredentials(), credentials, Map.of());
        reconciled = true;
        lastReceived = clock.millis();
      }
      socket.sendText("PING", true);
      var response =
          clob.heartbeat(auth.requireSignerCredentials(), auth.requireApiCreds(), heartbeatId);
      heartbeatId = response.path("heartbeat_id").asText();
      if (heartbeatId.isBlank())
        throw new IllegalStateException("Invalid heartbeat acknowledgement");
    } catch (Exception e) {
      reconciled = false;
      if (socket != null) socket.abort();
      socket = null;
    }
  }

  void receive(String text) {
    lastReceived = clock.millis();
    if (text.equalsIgnoreCase("PONG")) return;
    try {
      JsonNode node = mapper.readTree(text);
      if (node.isArray()) for (JsonNode event : node) dispatch(event);
      else dispatch(node);
    } catch (Exception e) {
      reconciled = false;
    }
  }

  private void dispatch(JsonNode node) {
    String type = node.path("event_type").asText();
    Set<String> ids = new HashSet<>();
    if (type.equals("order")) ids.add(node.path("id").asText());
    if (type.equals("trade")) {
      ids.add(node.path("taker_order_id").asText());
      for (JsonNode maker : node.path("maker_orders")) ids.add(maker.path("order_id").asText());
    }
    for (String id : ids)
      if (!id.isBlank()) reconciler.submit(() -> events.publishEvent(new OrderChanged(id)));
  }

  @PreDestroy
  void stop() {
    stopped = true;
    reconciled = false;
    if (socket != null) socket.abort();
    reconciler.shutdownNow();
  }

  private final class Listener implements WebSocket.Listener {
    private final StringBuilder buffer = new StringBuilder();

    public void onOpen(WebSocket ws) {
      ws.request(1);
    }

    public CompletionStage<?> onText(WebSocket ws, CharSequence data, boolean last) {
      buffer.append(data);
      if (buffer.length() > 1000000) {
        reconciled = false;
        ws.abort();
        return null;
      }
      if (last) {
        receive(buffer.toString());
        buffer.setLength(0);
      }
      ws.request(1);
      return null;
    }

    public CompletionStage<?> onClose(WebSocket ws, int code, String reason) {
      reconciled = false;
      socket = null;
      return null;
    }

    public void onError(WebSocket ws, Throwable error) {
      reconciled = false;
      socket = null;
    }
  }
}
