package com.polybot.hft.state;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class AtomicJsonStateTest {
  @TempDir Path dir;

  @Test
  void excludesSecondWriterAndAtomicallyRestores() {
    Path p = dir.resolve("state.json");
    var mapper = new ObjectMapper();
    try (var state = new AtomicJsonState(p, mapper)) {
      state.save(Map.of("cash", "100"));
      assertThatThrownBy(() -> new AtomicJsonState(p, mapper))
          .isInstanceOf(IllegalStateException.class);
      assertThat(state.load().path("cash").asText()).isEqualTo("100");
    }
    try (var restored = new AtomicJsonState(p, mapper)) {
      assertThat(restored.load().path("cash").asText()).isEqualTo("100");
    }
  }
}
