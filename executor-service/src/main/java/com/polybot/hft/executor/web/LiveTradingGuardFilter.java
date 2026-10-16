package com.polybot.hft.executor.web;

import com.polybot.hft.config.HftProperties;
import com.polybot.hft.domain.HftHeaders;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import lombok.RequiredArgsConstructor;
import org.jetbrains.annotations.NotNull;
import org.springframework.http.HttpMethod;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@RequiredArgsConstructor
public class LiveTradingGuardFilter extends OncePerRequestFilter {

  public static final String HEADER_LIVE_ACK = HftHeaders.LIVE_ACK;

  private final HftProperties properties;

  @Override
  protected boolean shouldNotFilter(HttpServletRequest request) {
    String uri = request.getRequestURI();
    if (uri == null || !uri.startsWith("/api/polymarket/orders")) {
      return true;
    }
    String method = request.getMethod();
    return HttpMethod.GET.matches(method)
        || HttpMethod.HEAD.matches(method)
        || HttpMethod.OPTIONS.matches(method);
  }

  @Override
  protected void doFilterInternal(
      @NotNull HttpServletRequest request,
      @NotNull HttpServletResponse response,
      @NotNull FilterChain filterChain)
      throws ServletException, IOException {
    if (properties.mode() == HftProperties.TradingMode.LIVE) {
      response.sendError(
          503,
          "LIVE rollout is locked pending verified account, user-stream and settlement parity");
      return;
    }

    filterChain.doFilter(request, response);
  }
}
