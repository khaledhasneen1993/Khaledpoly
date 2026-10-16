package com.polybot.hft.state;

import com.fasterxml.jackson.databind.*;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.*;
import java.nio.file.*;

/** Single writer; corruption or failed persistence stops execution. */
public final class AtomicJsonState implements AutoCloseable {
  private final Path path;
  private final ObjectMapper mapper;
  private final FileChannel channel;
  private final FileLock lock;

  public AtomicJsonState(Path path, ObjectMapper mapper) {
    this.path = path.toAbsolutePath();
    this.mapper = mapper;
    try {
      Files.createDirectories(this.path.getParent());
      channel =
          FileChannel.open(
              Path.of(this.path + ".lock"), StandardOpenOption.CREATE, StandardOpenOption.WRITE);
      lock = channel.tryLock();
      if (lock == null) throw new IllegalStateException("State already owned: " + path);
    } catch (IOException e) {
      throw new IllegalStateException("Cannot lock state", e);
    }
  }

  public synchronized JsonNode load() {
    try {
      if (!Files.exists(path)) return null;
      JsonNode data = mapper.readTree(Files.readAllBytes(path));
      if (data == null || !data.isObject())
        throw new IllegalStateException("State must be a JSON object");
      return data;
    } catch (IOException e) {
      throw new IllegalStateException("Unreadable state; refusing reset", e);
    }
  }

  public synchronized void save(Object state) {
    Path temp = Path.of(path + ".tmp");
    try {
      try (FileChannel out =
          FileChannel.open(
              temp,
              StandardOpenOption.CREATE,
              StandardOpenOption.TRUNCATE_EXISTING,
              StandardOpenOption.WRITE)) {
        ByteBuffer bytes = ByteBuffer.wrap(mapper.writeValueAsBytes(state));
        while (bytes.hasRemaining()) out.write(bytes);
        out.force(true);
      }
      try {
        Files.setPosixFilePermissions(
            temp, java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
      } catch (UnsupportedOperationException ignored) {
      }
      Files.move(temp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
      try (FileChannel dir = FileChannel.open(path.getParent(), StandardOpenOption.READ)) {
        dir.force(true);
      }
    } catch (IOException e) {
      throw new IllegalStateException("Durable write failed", e);
    }
  }

  public void close() {
    try {
      lock.release();
      channel.close();
    } catch (IOException e) {
      throw new IllegalStateException(e);
    }
  }
}
