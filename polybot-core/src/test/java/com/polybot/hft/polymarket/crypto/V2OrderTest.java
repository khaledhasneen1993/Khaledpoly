package com.polybot.hft.polymarket.crypto;

import static org.assertj.core.api.Assertions.*;

import com.polybot.hft.domain.OrderSide;
import com.polybot.hft.polymarket.model.OrderStatus;
import com.polybot.hft.polymarket.order.PolymarketOrderBuilder;
import java.math.BigDecimal;
import org.junit.jupiter.api.Test;
import org.web3j.crypto.Credentials;

class V2OrderTest {
  @Test
  void partialFillRemainsOpen() {
    assertThat(OrderStatus.terminal("PARTIALLY_FILLED")).isFalse();
    assertThat(OrderStatus.terminal("CANCELED")).isTrue();
  }

  @Test
  void signsCurrentStructAndRejectsOffGrid() {
    var builder = new PolymarketOrderBuilder(137, Credentials.create("1"), 0, null);
    var order =
        builder.buildLimitOrder(
            "123",
            OrderSide.BUY,
            new BigDecimal("0.50"),
            BigDecimal.TEN,
            new BigDecimal("0.01"),
            false,
            0,
            null,
            null,
            null);
    assertThat(order.timestamp()).isPositive();
    assertThat(order.signature()).startsWith("0x").hasSize(132);
    assertThatThrownBy(
            () ->
                builder.buildLimitOrder(
                    "123",
                    OrderSide.BUY,
                    new BigDecimal("0.501"),
                    BigDecimal.TEN,
                    new BigDecimal("0.01"),
                    false,
                    0,
                    null,
                    null,
                    null))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(
            () ->
                builder.buildLimitOrder(
                    "123",
                    OrderSide.BUY,
                    new BigDecimal("0.50"),
                    BigDecimal.TEN,
                    new BigDecimal("0.01"),
                    false,
                    10,
                    null,
                    null,
                    null))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void matchesIndependentTypedDataEncoding() throws Exception {
    var credentials = Credentials.create("1");
    String address = credentials.getAddress();
    String zero = "0x" + "00".repeat(32);
    String contract = "0xE111180000d2663C0091e4f400237545B87B996B";
    String typed =
        """
{"types":{"EIP712Domain":[{"name":"name","type":"string"},{"name":"version","type":"string"},{"name":"chainId","type":"uint256"},{"name":"verifyingContract","type":"address"}],
"Order":[{"name":"salt","type":"uint256"},{"name":"maker","type":"address"},{"name":"signer","type":"address"},{"name":"tokenId","type":"uint256"},{"name":"makerAmount","type":"uint256"},{"name":"takerAmount","type":"uint256"},{"name":"side","type":"uint8"},{"name":"signatureType","type":"uint8"},{"name":"timestamp","type":"uint256"},{"name":"metadata","type":"bytes32"},{"name":"builder","type":"bytes32"}]},
"primaryType":"Order","domain":{"name":"Polymarket CTF Exchange","version":"2","chainId":137,"verifyingContract":"%s"},
"message":{"salt":42,"maker":"%s","signer":"%s","tokenId":123,"makerAmount":5000000,"takerAmount":10000000,"side":0,"signatureType":0,"timestamp":1792140000000,"metadata":"%s","builder":"%s"}}
"""
            .formatted(contract, address, address, zero, zero);
    byte[] hash = new org.web3j.crypto.StructuredDataEncoder(typed).hashStructuredData();
    String signature =
        Eip712Signer.signOrderV2(
            credentials,
            137,
            contract,
            "42",
            address,
            address,
            "123",
            "5000000",
            "10000000",
            0,
            0,
            1792140000000L,
            zero,
            zero);
    byte[] sig = org.web3j.utils.Numeric.hexStringToByteArray(signature);
    var decoded =
        new org.web3j.crypto.Sign.SignatureData(
            sig[64],
            java.util.Arrays.copyOfRange(sig, 0, 32),
            java.util.Arrays.copyOfRange(sig, 32, 64));
    var recovered = org.web3j.crypto.Sign.signedMessageHashToKey(hash, decoded);
    assertThat("0x" + org.web3j.crypto.Keys.getAddress(recovered)).isEqualToIgnoringCase(address);
  }
}
