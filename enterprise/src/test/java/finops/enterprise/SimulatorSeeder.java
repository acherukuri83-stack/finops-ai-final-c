package finops.enterprise;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.testcontainers.containers.PostgreSQLContainer;

/**
 * Seeds a Testcontainers Postgres by shelling out to the real Python simulator
 * (`uv run python -m simulator.cli seed --scenario <n>`) rather than hand-typed SQL fixtures —
 * per CLAUDE.md's definition of done, "contract tests pass against seeded scenario data (not
 * mocks)". `simulator/simulator/cli.py`'s seed command truncates and repopulates the whole
 * schema (baseline.populate) before planting the requested scenario, so this is safe to call
 * once per test method against a shared container.
 *
 * <p>Requires {@code uv} on PATH and Docker reachable for Testcontainers to pull the Postgres
 * image — CI's verify.yml runs `uv sync` before `scripts/verify.sh` invokes `mvn test`, so both
 * are true there. Neither is true in the sandbox this was written in (Maven Central and Docker
 * Hub are both egress-blocked), so this class has not actually been exercised — see the PR
 * body's "How I validated" section for exactly what was and wasn't run.
 */
final class SimulatorSeeder {
  private SimulatorSeeder() {}

  static void seed(PostgreSQLContainer<?> postgres, String scenario) {
    Path simulatorDir = findSimulatorDir();
    String databaseUrl =
        "postgresql+psycopg://"
            + postgres.getUsername()
            + ":"
            + postgres.getPassword()
            + "@"
            + postgres.getHost()
            + ":"
            + postgres.getMappedPort(5432)
            + "/"
            + postgres.getDatabaseName();
    ProcessBuilder pb =
        new ProcessBuilder(
            "uv", "run", "python", "-m", "simulator.cli", "seed", "--scenario", scenario);
    pb.directory(simulatorDir.toFile());
    pb.environment().put("DATABASE_URL", databaseUrl);
    pb.redirectErrorStream(true);
    try {
      Process p = pb.start();
      String output = new String(p.getInputStream().readAllBytes());
      int exit = p.waitFor();
      if (exit != 0) {
        throw new IllegalStateException(
            "simulator seed --scenario " + scenario + " failed (exit " + exit + "):\n" + output);
      }
    } catch (IOException e) {
      throw new IllegalStateException("failed to invoke simulator seed --scenario " + scenario, e);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new IllegalStateException("interrupted seeding scenario " + scenario, e);
    }
  }

  /** Walks up from the test's working directory to find the sibling simulator/ package. */
  private static Path findSimulatorDir() {
    Path dir = Path.of("").toAbsolutePath();
    for (int i = 0; i < 6 && dir != null; i++) {
      Path candidate = dir.resolve("simulator");
      if (Files.isDirectory(candidate) && Files.exists(candidate.resolve("pyproject.toml"))) {
        return candidate;
      }
      dir = dir.getParent();
    }
    throw new IllegalStateException(
        "could not locate simulator/ from " + Path.of("").toAbsolutePath());
  }
}
