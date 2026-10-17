package com.polybot.hft.paper;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.zip.GZIPInputStream;

/** Transparent storage compression; the logical journal sequence and timestamps are unchanged. */
public final class TapeIO {
  private TapeIO() {}
  public static BufferedReader reader(Path path) throws IOException {
    InputStream stream = Files.newInputStream(path);
    try {
      if (path.toString().endsWith(".gz")) stream = new GZIPInputStream(stream, 64 * 1024);
      return new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8), 64 * 1024);
    } catch (IOException error) { stream.close(); throw error; }
  }
}
