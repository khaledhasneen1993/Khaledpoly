package com.polybot.hft.polymarket.api;

public record PaperPairRequest(LimitOrderRequest up, LimitOrderRequest down) {}
