package finops.enterprise;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

/**
 * Scenario 12 (tool_outage): FAULT_INJECT is read once at context startup by
 * FaultInjectionFilter, so this needs its own Spring context rather than sharing
 * ScenarioContractTest's — set via @DynamicPropertySource, which the filter's
 * {@code @Value("${FAULT_INJECT:}")} picks up like any other Spring property.
 *
 * <p>Not executed in this sandbox — see ScenarioContractTest's javadoc.
 */
@Testcontainers
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class FaultInjectionTest {

  @Container
  @ServiceConnection
  static PostgreSQLContainer<?> postgres =
      new PostgreSQLContainer<>(
          DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));

  @DynamicPropertySource
  static void faultInject(DynamicPropertyRegistry registry) {
    registry.add("FAULT_INJECT", () -> "trade.settlement_status:503");
  }

  @LocalServerPort private int port;
  @Autowired private TestRestTemplate rest;

  private String url(String path) {
    return "http://localhost:" + port + path;
  }

  @Test
  void settlementStatusIsDegradedButOtherToolsStillWork() {
    SimulatorSeeder.seed(postgres, "12");

    ResponseEntity<String> degraded =
        rest.getForEntity(url("/trades/T100245/settlement"), String.class);
    assertThat(degraded.getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
    assertThat(degraded.getBody()).contains("retryable");

    // The fault is scoped to get_settlement_status only — everything else the agent needs for
    // a provisional root cause (Sc. 12's expect block) must still be reachable.
    ResponseEntity<TradeDto> trade = rest.getForEntity(url("/trades/T100245"), TradeDto.class);
    assertThat(trade.getStatusCode()).isEqualTo(HttpStatus.OK);

    ResponseEntity<SsiDto[]> history =
        rest.getForEntity(url("/accounts/ACC-88213/ssi/history"), SsiDto[].class);
    assertThat(history.getStatusCode()).isEqualTo(HttpStatus.OK);
    assertThat(history.getBody()).hasSizeGreaterThanOrEqualTo(3);

    ResponseEntity<AffirmationDto> aff =
        rest.getForEntity(url("/trades/T100245/affirmation"), AffirmationDto.class);
    assertThat(aff.getStatusCode()).isEqualTo(HttpStatus.OK);
    assertThat(aff.getBody().cptyDtc()).isEqualTo("5678");
  }
}
