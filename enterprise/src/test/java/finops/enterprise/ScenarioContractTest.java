package finops.enterprise;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

/**
 * Every endpoint against real seeded scenario data (docs/eval-scenarios.md), asserting specific
 * planted values per PR2's validate checklist — not shapes, not mocks. Scenario 12 (fault
 * injection) gets its own test class since FAULT_INJECT is fixed per Spring context.
 *
 * <p>NOT executed in the sandbox this was authored in: Testcontainers needs to pull
 * pgvector/pgvector:pg16 from Docker Hub, which is egress-blocked there. Needs a real run
 * (CI or a normal-network machine) before merge — see the PR body.
 */
@Testcontainers
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ScenarioContractTest {

  // pgvector/pgvector is postgres-compatible but isn't the "postgres" image PostgreSQLContainer
  // validates against by default — asCompatibleSubstituteFor tells it that's fine.
  @Container
  @ServiceConnection
  static PostgreSQLContainer<?> postgres =
      new PostgreSQLContainer<>(
          DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));

  @LocalServerPort private int port;
  @org.springframework.beans.factory.annotation.Autowired private TestRestTemplate rest;

  private String url(String path) {
    return "http://localhost:" + port + path;
  }

  private <T> T get(String path, Class<T> type) {
    ResponseEntity<T> resp = rest.getForEntity(url(path), type);
    assertThat(resp.getStatusCode()).isEqualTo(HttpStatus.OK);
    return resp.getBody();
  }

  @Test
  void scenario1CounterpartySsiStale() {
    SimulatorSeeder.seed(postgres, "1");

    TradeDto trade = get("/trades/T100245", TradeDto.class);
    assertThat(trade.status()).isEqualTo("FAILED");

    SsiDto current = get("/accounts/ACC-88213/ssi", SsiDto.class);
    assertThat(current.dtcParticipant()).isEqualTo("1234");
    assertThat(current.version()).isEqualTo(3);

    SsiDto[] history = get("/accounts/ACC-88213/ssi/history", SsiDto[].class);
    assertThat(history).hasSizeGreaterThanOrEqualTo(3);
    assertThat(history).anySatisfy(v -> assertThat(v.dtcParticipant()).isEqualTo("9012"));

    CptySsiDto cptySsi = get("/counterparties/CP-017/ssi", CptySsiDto.class);
    assertThat(cptySsi.dtcParticipant()).isEqualTo("5678");

    AffirmationDto aff = get("/trades/T100245/affirmation", AffirmationDto.class);
    assertThat(aff.cptyDtc()).isEqualTo("5678");

    SettlementStatusDto settlement = get("/trades/T100245/settlement", SettlementStatusDto.class);
    assertThat(settlement.failureCode()).isEqualTo("COUNTERPARTY_SSI_MISMATCH");
    assertThat(settlement.attempts()).isNotEmpty();
  }

  @Test
  void scenario2ClientSsiStale() {
    SimulatorSeeder.seed(postgres, "2");

    SsiDto current = get("/accounts/ACC-88213/ssi", SsiDto.class);
    assertThat(current.dtcParticipant()).isEqualTo("5678");

    CptySsiDto cptySsi = get("/counterparties/CP-017/ssi", CptySsiDto.class);
    assertThat(cptySsi.dtcParticipant()).isEqualTo("1234");

    AffirmationDto aff = get("/trades/T100245/affirmation", AffirmationDto.class);
    assertThat(aff.cptyDtc()).isEqualTo("1234");

    SettlementStatusDto settlement = get("/trades/T100245/settlement", SettlementStatusDto.class);
    assertThat(settlement.failureCode()).isEqualTo("COUNTERPARTY_SSI_MISMATCH");
  }

  @Test
  void scenario3SecurityReferenceError() {
    SimulatorSeeder.seed(postgres, "3");

    SecurityDto xyzq = get("/securities/XYZQ", SecurityDto.class);
    assertThat(xyzq.isin()).isEqualTo("US98765XYZQ1");
    assertThat(xyzq.cusip()).isEqualTo("98765XYZ1");

    SettlementStatusDto settlement = get("/trades/T100250/settlement", SettlementStatusDto.class);
    assertThat(settlement.failureCode()).isEqualTo("SECURITY_ID_MISMATCH");

    LogEntryDto[] logs = get("/logs?tradeId=T100250", LogEntryDto[].class);
    assertThat(logs).anySatisfy(l -> assertThat(l.msg()).contains("98765XYZ9"));
  }

  @Test
  void scenario5InsufficientPosition() {
    SimulatorSeeder.seed(postgres, "5");

    PositionDto pos = get("/positions?account=ACC-88213&security=NVDA", PositionDto.class);
    assertThat(pos.qty()).isEqualTo(40000L);
    assertThat(pos.available()).isEqualTo(15000L);
    assertThat(pos.pendingDeliver()).isEqualTo(25000L);

    BorrowAvailabilityDto borrow = get("/borrow/NVDA", BorrowAvailabilityDto.class);
    assertThat(borrow.availableQty()).isEqualTo(100000L);

    SettlementStatusDto settlement = get("/trades/T100270/settlement", SettlementStatusDto.class);
    assertThat(settlement.failureCode()).isEqualTo("INSUFFICIENT_POSITION");
  }

  @Test
  void scenario6CounterpartyInstructionExpired() {
    SimulatorSeeder.seed(postgres, "6");

    CptySsiDto cptySsi = get("/counterparties/CP-017/ssi", CptySsiDto.class);
    assertThat(cptySsi.validTo()).isEqualTo(LocalDate.of(2026, 8, 31));

    SettlementStatusDto settlement = get("/trades/T100283/settlement", SettlementStatusDto.class);
    assertThat(settlement.failureCode()).isEqualTo("COUNTERPARTY_SSI_MISMATCH");
  }

  @Test
  void scenario8DuplicateTrade() {
    SimulatorSeeder.seed(postgres, "8");

    TradeDto t290 = get("/trades/T100290", TradeDto.class);
    assertThat(t290.status()).isEqualTo("SETTLED");

    TradeDto t291 = get("/trades/T100291", TradeDto.class);
    assertThat(t291.status()).isEqualTo("FAILED");
    SettlementStatusDto t291Settlement =
        get("/trades/T100291/settlement", SettlementStatusDto.class);
    assertThat(t291Settlement.failureCode()).isEqualTo("DUPLICATE_SUSPECT");

    TradeDto[] related = get("/trades?account=ACC-88213&security=GOOGL", TradeDto[].class);
    assertThat(related).extracting(TradeDto::tradeId).contains("T100290", "T100291");
  }

  @Test
  void scenario9AlreadyRemediated() {
    SimulatorSeeder.seed(postgres, "9");

    // The contract's get_affirmation returns one Affirmation per trade — enterprise resolves
    // that to the latest by affirmed_at, so this must reflect the re-affirmation (1234), not
    // the original mismatched one (5678), even though both rows exist in settlement_attempts
    // history.
    AffirmationDto aff = get("/trades/T100245/affirmation", AffirmationDto.class);
    assertThat(aff.cptyDtc()).isEqualTo("1234");

    SsiDto[] history = get("/accounts/ACC-88213/ssi/history", SsiDto[].class);
    assertThat(history).hasSizeGreaterThanOrEqualTo(3);
  }

  @Test
  void scenario10NoEvidence() {
    SimulatorSeeder.seed(postgres, "10");

    SettlementStatusDto settlement = get("/trades/T100299/settlement", SettlementStatusDto.class);
    assertThat(settlement.failureCode()).isEqualTo("UNKNOWN");
    assertThat(settlement.failureDetail()).isNull();

    // Sc. 10 plants zero corroborating log lines by design (final-plan.md: "Sc. 10: none").
    LogEntryDto[] logs = get("/logs?tradeId=T100299", LogEntryDto[].class);
    assertThat(logs).isEmpty();
  }
}
