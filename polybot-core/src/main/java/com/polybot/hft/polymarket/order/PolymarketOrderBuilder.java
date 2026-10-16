package com.polybot.hft.polymarket.order;

import com.polybot.hft.domain.OrderSide;
import com.polybot.hft.polymarket.crypto.Eip712Signer;
import com.polybot.hft.polymarket.model.SignedOrder;
import com.polybot.hft.polymarket.onchain.ContractConfig;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.Objects;
import org.web3j.crypto.Credentials;

public final class PolymarketOrderBuilder {

  private static final String ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";

  private final int chainId;
  private String marketVersion = "v1";
  private final Credentials signerCredentials;
  private final int signatureType;
  private final String funderAddress;

  public PolymarketOrderBuilder(
      int chainId, Credentials signerCredentials, int signatureType, String funderAddress) {
    this.chainId = chainId;
    this.signerCredentials = Objects.requireNonNull(signerCredentials, "signerCredentials");
    this.signatureType = signatureType;
    this.funderAddress = (funderAddress == null || funderAddress.isBlank()) ? null : funderAddress;
  }

  public static PolymarketOrderBuilder forMarket(
      int chainId, Credentials credentials, int signatureType, String funder, String version) {
    if (chainId != 137)
      throw new IllegalArgumentException("Current contracts are verified for Polygon mainnet only");
    com.polybot.hft.polymarket.onchain.ProtocolContracts.resolve(version, false);
    var builder = new PolymarketOrderBuilder(chainId, credentials, signatureType, funder);
    builder.marketVersion = version;
    return builder;
  }

  private static void validatePrice(BigDecimal price, BigDecimal tickSize) {
    if (price == null) {
      throw new IllegalArgumentException("price must not be null");
    }
    if (tickSize == null) {
      throw new IllegalArgumentException("tickSize must not be null");
    }
    if (tickSize.signum() <= 0 || price.remainder(tickSize).signum() != 0) {
      throw new IllegalArgumentException("Price must be an exact multiple of a positive tick size");
    }
    BigDecimal min = tickSize;
    BigDecimal max = BigDecimal.ONE.subtract(tickSize);
    if (price.compareTo(min) < 0 || price.compareTo(max) > 0) {
      throw new IllegalArgumentException("price must be within [" + min + ", " + max + "]");
    }
  }

  private static int decimalPlaces(BigDecimal value) {
    BigDecimal stripped = value.stripTrailingZeros();
    return Math.max(0, stripped.scale());
  }

  private static BigDecimal roundNormal(BigDecimal value, int decimals) {
    if (decimalPlaces(value) <= decimals) {
      return value;
    }
    return value.setScale(decimals, RoundingMode.HALF_UP);
  }

  private static BigDecimal roundDown(BigDecimal value, int decimals) {
    if (decimalPlaces(value) <= decimals) {
      return value;
    }
    return value.setScale(decimals, RoundingMode.DOWN);
  }

  private static BigDecimal roundUp(BigDecimal value, int decimals) {
    if (decimalPlaces(value) <= decimals) {
      return value;
    }
    return value.setScale(decimals, RoundingMode.UP);
  }

  private static BigDecimal clampAmountDecimals(BigDecimal amount, int maxDecimals) {
    if (decimalPlaces(amount) <= maxDecimals) {
      return amount;
    }

    BigDecimal roundedUp = roundUp(amount, maxDecimals + 4);
    if (decimalPlaces(roundedUp) > maxDecimals) {
      return roundDown(roundedUp, maxDecimals);
    }
    return roundedUp;
  }

  private static BigInteger toBaseUnits(BigDecimal amount, int decimals) {
    if (decimalPlaces(amount) > decimals) {
      throw new IllegalArgumentException(
          "Amount has more than " + decimals + " decimals: " + amount);
    }
    BigDecimal scaled = amount.movePointRight(decimals);
    return scaled.setScale(0, RoundingMode.UNNECESSARY).toBigIntegerExact();
  }

  public SignedOrder buildLimitOrder(
      String tokenId,
      OrderSide side,
      BigDecimal price,
      BigDecimal size,
      BigDecimal tickSize,
      boolean negRisk,
      Integer feeRateBps,
      Long nonce,
      Long expirationSeconds,
      String taker) {
    validatePrice(price, tickSize);

    RoundConfig roundConfig = RoundConfig.fromTickSize(tickSize);
    BigDecimal rawPrice = roundNormal(price, roundConfig.priceDecimals());

    BigDecimal rawMakerAmt;
    BigDecimal rawTakerAmt;
    if (side == OrderSide.BUY) {
      rawTakerAmt = roundDown(size, roundConfig.sizeDecimals());
      rawMakerAmt = rawTakerAmt.multiply(rawPrice);
      rawMakerAmt = clampAmountDecimals(rawMakerAmt, roundConfig.amountDecimals());
    } else {
      rawMakerAmt = roundDown(size, roundConfig.sizeDecimals());
      rawTakerAmt = rawMakerAmt.multiply(rawPrice);
      rawTakerAmt = clampAmountDecimals(rawTakerAmt, roundConfig.amountDecimals());
    }

    return signOrder(
        tokenId,
        side,
        toBaseUnits(rawMakerAmt, ContractConfig.forChainId(chainId).collateralTokenDecimals()),
        toBaseUnits(rawTakerAmt, ContractConfig.forChainId(chainId).collateralTokenDecimals()),
        negRisk,
        feeRateBps,
        nonce,
        expirationSeconds,
        taker);
  }

  public SignedOrder buildMarketOrder(
      String tokenId,
      OrderSide side,
      BigDecimal amount,
      BigDecimal price,
      BigDecimal tickSize,
      boolean negRisk,
      Integer feeRateBps,
      Long nonce,
      String taker) {
    validatePrice(price, tickSize);

    RoundConfig roundConfig = RoundConfig.fromTickSize(tickSize);
    BigDecimal rawPrice = roundDown(price, roundConfig.priceDecimals());

    BigDecimal rawMakerAmt;
    BigDecimal rawTakerAmt;
    if (side == OrderSide.BUY) {
      rawMakerAmt = roundDown(amount, roundConfig.sizeDecimals());
      rawTakerAmt =
          rawMakerAmt.divide(rawPrice, roundConfig.amountDecimals() + 12, RoundingMode.HALF_UP);
      rawTakerAmt = clampAmountDecimals(rawTakerAmt, roundConfig.amountDecimals());
    } else {
      rawMakerAmt = roundDown(amount, roundConfig.sizeDecimals());
      rawTakerAmt = rawMakerAmt.multiply(rawPrice);
      rawTakerAmt = clampAmountDecimals(rawTakerAmt, roundConfig.amountDecimals());
    }

    return signOrder(
        tokenId,
        side,
        toBaseUnits(rawMakerAmt, ContractConfig.forChainId(chainId).collateralTokenDecimals()),
        toBaseUnits(rawTakerAmt, ContractConfig.forChainId(chainId).collateralTokenDecimals()),
        negRisk,
        feeRateBps,
        nonce,
        0L,
        taker);
  }

  private SignedOrder signOrder(
      String tokenId,
      OrderSide side,
      BigInteger makerAmount,
      BigInteger takerAmount,
      boolean negRisk,
      Integer feeRateBps,
      Long nonce,
      Long expirationSeconds,
      String taker) {
    ContractConfig contractConfig = ContractConfig.forChainId(chainId);
    var protocol =
        com.polybot.hft.polymarket.onchain.ProtocolContracts.resolve(marketVersion, negRisk);
    if (chainId != 137)
      throw new IllegalArgumentException("V2/V3 contract configuration requires Polygon mainnet");
    String exchangeContract = protocol.exchange();

    String signerAddress = signerCredentials.getAddress();
    String makerAddress = (funderAddress == null) ? signerAddress : funderAddress;
    String takerAddress = (taker == null || taker.isBlank()) ? ZERO_ADDRESS : taker;

    if (signatureType < 0 || signatureType > 2)
      throw new IllegalArgumentException(
          "Deposit-wallet signatures require a dedicated verified adapter");
    if ((feeRateBps != null && feeRateBps != 0)
        || (nonce != null && nonce != 0)
        || (taker != null && !taker.equalsIgnoreCase(ZERO_ADDRESS))) {
      throw new IllegalArgumentException(
          "Legacy nonce, taker and embedded fees are unsupported in CLOB V2");
    }
    String salt = new BigInteger(256, new java.security.SecureRandom()).toString();
    long timestamp = Instant.now().toEpochMilli();
    String zero32 = "0x" + "00".repeat(32);
    String signature =
        Eip712Signer.signOrderVersion(
            signerCredentials,
            chainId,
            exchangeContract,
            salt,
            makerAddress,
            signerAddress,
            tokenId,
            makerAmount.toString(),
            takerAmount.toString(),
            side.toEip712Value(),
            signatureType,
            timestamp,
            zero32,
            zero32,
            protocol.domainVersion());
    return new SignedOrder(
        salt,
        makerAddress,
        signerAddress,
        ZERO_ADDRESS,
        tokenId,
        makerAmount.toString(),
        takerAmount.toString(),
        Long.toString(expirationSeconds == null ? 0L : expirationSeconds),
        "0",
        "0",
        side,
        signatureType,
        signature,
        timestamp,
        zero32,
        zero32);
  }

  private record RoundConfig(int priceDecimals, int sizeDecimals, int amountDecimals) {
    static RoundConfig fromTickSize(BigDecimal tickSize) {
      int priceDecimals = Math.max(0, tickSize.stripTrailingZeros().scale());
      return new RoundConfig(priceDecimals, 2, priceDecimals + 2);
    }
  }
}
