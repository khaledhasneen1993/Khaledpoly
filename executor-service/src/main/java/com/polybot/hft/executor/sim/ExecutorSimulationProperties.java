package com.polybot.hft.executor.sim;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Legacy probability knobs are removed. Every enabled fill requires an observed opposing print. */
@ConfigurationProperties(prefix = "executor.sim")
public record ExecutorSimulationProperties(
    Boolean enabled, String username, String proxyAddress, Boolean fillsEnabled) {
  public ExecutorSimulationProperties {
    if (enabled == null) enabled = false;
    if (username == null || username.isBlank()) username = "polybot-sim";
    if (proxyAddress == null || proxyAddress.isBlank()) proxyAddress = "sim";
    if (fillsEnabled == null) fillsEnabled = false;
  }
}
