package finops.enterprise;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class HealthControllerTest {
  @Test
  void healthReportsOk() {
    assertThat(new HealthController().health()).containsEntry("status", "ok");
  }
}
