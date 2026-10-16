package com.polybot.hft.polymarket.onchain;

public record ContractConfig(
    String exchange,
    String negRiskAdapter,
    String negRiskExchange,
    String collateral,
    String conditionalTokens,
    int collateralTokenDecimals,
    int conditionalTokenDecimals) {
  public static String tradingCollateral() {
    return "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB";
  }

  public static String collateralAdapter() {
    return "0xAdA100Db00Ca00073811820692005400218FcE1f";
  }

  public static ContractConfig forChainId(int chainId) {
    return switch (chainId) {
      case 137 ->
          new ContractConfig(
              "0xE111180000d2663C0091e4f400237545B87B996B",
              "0xadA2005600Dec949baf300f4C6120000bDB6eAab",
              "0xe2222d279d744050d28e00520010520000310F59",
              "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
              "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
              6,
              6);
      case 80002 ->
          new ContractConfig(
              "0xdFE02Eb6733538f8Ea35D585af8DE5958AD99E40",
              "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
              "0xe2222d279d744050d28e00520010520000310F59",
              "0x9c4e1703476e875070ee25b56a58b008cfb8fa78",
              "0x69308FB512518e39F9b16112fA8d994F4e2Bf8bB",
              6,
              6);
      default -> throw new IllegalArgumentException("Unsupported chainId: " + chainId);
    };
  }
}
