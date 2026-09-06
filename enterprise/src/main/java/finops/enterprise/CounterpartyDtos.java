package finops.enterprise;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Counterparty.contacts[] has no backing table in the Phase A schema — always empty; noted in
 * the PR body. No scenario needs contact data.
 */
record CounterpartyDto(String cptyId, String name, String status, List<String> contacts) {}

record CptySsiDto(String cptyId, String dtcParticipant, LocalDate validTo) {
  static CptySsiDto from(CounterpartySsi s) {
    return new CptySsiDto(s.cptyId, s.dtcParticipant, s.validTo);
  }
}

record AffirmationDto(
    String tradeId, String cptyId, Boolean affirmed, String cptyDtc, LocalDateTime affirmedAt) {
  static AffirmationDto from(Affirmation a) {
    return new AffirmationDto(a.tradeId, a.cptyId, a.affirmed, a.cptyDtc, a.affirmedAt);
  }
}
