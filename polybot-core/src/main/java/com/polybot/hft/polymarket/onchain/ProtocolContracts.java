package com.polybot.hft.polymarket.onchain;

/** Position protocol and CLOB generation are separate concepts. Polygon mainnet only. */
public record ProtocolContracts(
    String exchange, String domainVersion, String positions, String target) {
  public static ProtocolContracts resolve(String version, boolean negativeRisk) {
    return switch (version) {
      case "v1" ->
          new ProtocolContracts(
              negativeRisk
                  ? "0xe2222d279d744050d28e00520010520000310F59"
                  : "0xE111180000d2663C0091e4f400237545B87B996B",
              "2",
              "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
              negativeRisk
                  ? "0xadA2005600Dec949baf300f4C6120000bDB6eAab"
                  : "0xAdA100Db00Ca00073811820692005400218FcE1f");
      case "v2" ->
          new ProtocolContracts(
              "0xe3333700cA9d93003F00f0F71f8515005F6c00Aa",
              "3",
              "0x006F54F7f9A22e0000CC2AB60031000000ae9fEF",
              "0x12121212006e4CD160D18e3f00711DA5c3372600");
      default -> throw new IllegalArgumentException("Unsupported position protocol");
    };
  }
}
