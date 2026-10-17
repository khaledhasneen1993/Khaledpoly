package com.polybot.hft.paper;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.util.HashSet;
import java.util.Set;

/** Public V2 CLOB parameters; unknown fee/membership information is never inferred by category. */
public record ClobMarketParameters(
    BigDecimal tick, BigDecimal minimum, FeeModel fees, boolean accepting) {
  public static ClobMarketParameters parse(
      JsonNode n, String condition, Set<String> expectedTokens) {
    String actual = n.hasNonNull("c") ? n.path("c").asText() : n.path("condition_id").asText();
    if ((!actual.isEmpty() && !actual.equals(condition)) || !n.path("t").isArray())
      throw new IllegalArgumentException("V2 condition identity mismatch");
    var tokens = new HashSet<String>();
    for (var token : n.path("t"))
      if (!token.path("t").isTextual()
          || token.path("t").asText().isBlank()
          || !tokens.add(token.path("t").asText()))
        throw new IllegalArgumentException("Invalid V2 token membership");
    if (!tokens.equals(expectedTokens) || n.path("nr").asBoolean(false))
      throw new IllegalArgumentException("Unsupported V2 token/risk universe");
    BigDecimal tick = decimal(n, "mts"), minimum = decimal(n, "mos");
    if (tick.signum() <= 0 || tick.compareTo(BigDecimal.ONE) >= 0 || minimum.signum() <= 0)
      throw new IllegalArgumentException("Invalid V2 lot/tick");
    var fd = n.path("fd");
    FeeModel fees;
    if (fd.isObject()) {
      BigDecimal exponent = decimal(fd, "e");
      fees = new FeeModel(decimal(fd, "r"), exponent.intValueExact());
      if (fees.rate().signum() > 0 && (!fd.path("to").isBoolean() || !fd.path("to").asBoolean()))
        throw new IllegalArgumentException("Unsupported maker fee schedule");
    } else if (n.hasNonNull("tbf")
        && n.hasNonNull("mbf")
        && decimal(n, "tbf").signum() == 0
        && decimal(n, "mbf").signum() == 0) {
      fees = new FeeModel(BigDecimal.ZERO, 1);
    } else throw new IllegalArgumentException("Missing V2 fee evidence");
    // An omitted acceptance flag is unknown, so it never authorizes entry.
    return new ClobMarketParameters(
        tick, minimum, fees, n.path("ao").isBoolean() && n.path("ao").asBoolean());
  }

  private static BigDecimal decimal(JsonNode n, String key) {
    if (!n.hasNonNull(key) || n.path(key).isBoolean())
      throw new IllegalArgumentException("Missing V2 parameter " + key);
    return new BigDecimal(n.path(key).asText());
  }
}
