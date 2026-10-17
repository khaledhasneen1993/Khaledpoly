package com.polybot.hft.executor.web;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.ByteArrayInputStream;
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
    if ((req.getRequestURI().equals("/api/research/v1/proposals/screen")
            || req.getRequestURI().equals("/api/research/v1/proposals/paper")
            || req.getRequestURI().equals("/api/research/v1/proposals/settle-paper-group"))
        && req.getMethod().equals("POST")) {
      byte[] body = req.getInputStream().readNBytes(65537);
      if (body.length > 65536) {
        resp.sendError(413);
        return;
      }
      var input = new ByteArrayInputStream(body);
      var wrapped =
          new HttpServletRequestWrapper(req) {
            @Override
            public ServletInputStream getInputStream() {
              return new ServletInputStream() {
                @Override
                public int read() {
                  return input.read();
                }

                @Override
                public int read(byte[] target, int offset, int length) {
                  return input.read(target, offset, length);
                }

                @Override
                public boolean isFinished() {
                  return input.available() == 0;
                }

                @Override
                public boolean isReady() {
                  return true;
                }

                @Override
                public void setReadListener(ReadListener listener) {
                  throw new IllegalStateException("Asynchronous research bodies unsupported");
                }
              };
            }

            @Override
            public int getContentLength() {
              return body.length;
            }

            @Override
            public long getContentLengthLong() {
              return body.length;
            }
          };
      chain.doFilter(wrapped, resp);
      return;
    }
    chain.doFilter(req, resp);
  }
}
