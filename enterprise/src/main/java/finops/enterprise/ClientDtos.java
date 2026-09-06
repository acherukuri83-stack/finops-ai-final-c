package finops.enterprise;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Field names match docs/tool-contracts.md's Client / Account / SSI shapes. Two fields
 * (Client.restrictions aggregated across accounts; Account.riskFlags) have no backing data in
 * the Phase A schema (V2__phase_a_schema.sql has no risk-flag table) — riskFlags is always
 * empty for now; noted in the PR body rather than changing the contract doc, since no scenario
 * in docs/eval-scenarios.md exercises it.
 */
record ClientDto(String clientId, String name, String type, String status, List<RestrictionDto> restrictions) {}

record AccountDto(
    String accountId,
    String clientId,
    String custodian,
    String status,
    List<RestrictionDto> restrictions,
    List<String> riskFlags) {}

record SsiDto(
    String accountId,
    Integer version,
    String dtcParticipant,
    String agentBic,
    LocalDate validFrom,
    LocalDate validTo,
    LocalDateTime updatedAt,
    String updatedBy) {
  static SsiDto from(SsiVersion v) {
    return new SsiDto(
        v.accountId, v.version, v.dtcParticipant, v.agentBic, v.validFrom, v.validTo, v.updatedAt, v.updatedBy);
  }
}

record SsiUpdateRequest(String dtcParticipant, String agentBic, LocalDate validFrom, String updatedBy) {}
