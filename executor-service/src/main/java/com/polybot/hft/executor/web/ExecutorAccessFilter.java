package com.polybot.hft.executor.web;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class ExecutorAccessFilter extends OncePerRequestFilter {
  @Value("${polybot.executor-token:}")
  private String token;

  @Override
  protected void doFilterInternal(
      HttpServletRequest req, HttpServletResponse resp, FilterChain chain)
      throws ServletException, IOException {
    if (req.getRequestURI().startsWith("/api/") && !token.isBlank()) {
      String supplied = req.getHeader("X-Polybot-Token");
      if (supplied == null
          || !MessageDigest.isEqual(
              token.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8))) {
        resp.sendError(401);
        return;
      }
    }
    chain.doFilter(req, resp);
  }
}
