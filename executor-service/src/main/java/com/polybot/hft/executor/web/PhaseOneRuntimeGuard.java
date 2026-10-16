package com.polybot.hft.executor.web;

import com.polybot.hft.config.HftProperties;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class PhaseOneRuntimeGuard {
  private final HftProperties properties;

  @org.springframework.beans.factory.annotation.Value("${server.address:127.0.0.1}")
  private String bind;

  @org.springframework.beans.factory.annotation.Value("${polybot.executor-token:}")
  private String token;

  @PostConstruct
  void validate() {
    if (!java.util.Set.of("127.0.0.1", "::1", "localhost").contains(bind) && token.isBlank())
      throw new IllegalStateException("A non-loopback executor requires POLYBOT_EXECUTOR_TOKEN");
    if (properties.mode() != HftProperties.TradingMode.PAPER)
      throw new IllegalStateException(
          "This phase-one release is PAPER-only; live parity is not validated");
  }
}
