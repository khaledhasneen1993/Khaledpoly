package com.polybot.hft.executor.settlement;

import com.polybot.hft.polymarket.onchain.*;
import java.math.BigInteger;
import java.util.*;
import org.web3j.abi.FunctionEncoder;
import org.web3j.abi.datatypes.*;
import org.web3j.abi.datatypes.generated.*;
import org.web3j.utils.Numeric;

public final class PositionCallPlanner {
  public record Call(String target, String data) {}

  private PositionCallPlanner() {}

  public static Call merge(String version, boolean negRisk, String condition, BigInteger amount) {
    if (amount.signum() <= 0) throw new IllegalArgumentException("Positive merge amount required");
    var contracts = ProtocolContracts.resolve(version, negRisk);
    if (version.equals("v1"))
      return new Call(
          contracts.target(),
          ConditionalTokensCallEncoder.encodeMergePositions(
              ContractConfig.tradingCollateral(),
              condition,
              List.of(BigInteger.ONE, BigInteger.TWO),
              amount));
    return new Call(
        contracts.target(),
        FunctionEncoder.encode(
            new Function("merge", List.of(id31(condition), new Uint256(amount)), List.of())));
  }

  public static Call redeem(
      String version, boolean negRisk, String condition, int outcome, BigInteger amount) {
    var contracts = ProtocolContracts.resolve(version, negRisk);
    if (version.equals("v1"))
      return new Call(
          contracts.target(),
          ConditionalTokensCallEncoder.encodeRedeemPositions(
              ContractConfig.tradingCollateral(),
              condition,
              List.of(BigInteger.ONE, BigInteger.TWO)));
    if (outcome < 0 || outcome > 1 || amount.signum() <= 0)
      throw new IllegalArgumentException("Invalid outcome or amount");
    return new Call(
        contracts.target(),
        FunctionEncoder.encode(
            new Function(
                "redeem",
                List.of(id31(condition), new Uint256(outcome), new Uint256(amount)),
                List.of())));
  }

  private static Bytes31 id31(String condition) {
    byte[] value = Numeric.hexStringToByteArray(condition);
    // Data API emits canonical 32-byte IDs; leading padding is not part of bytes31 protocol ID.
    if (value.length == 32 && value[0] == 0) value = Arrays.copyOfRange(value, 1, 32);
    if (value.length != 31)
      throw new IllegalArgumentException("V2 structural condition ID must be bytes31");
    return new Bytes31(value);
  }
}
