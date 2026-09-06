package finops.enterprise;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDate;
import java.time.LocalDateTime;

/** `ssi_versions` and `counterparty_ssi` — see V2__phase_a_schema.sql. */
@Entity
@Table(name = "ssi_versions")
class SsiVersion {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  Long id;

  @Column(name = "account_id")
  String accountId;

  Integer version;

  @Column(name = "dtc_participant")
  String dtcParticipant;

  @Column(name = "agent_bic")
  String agentBic;

  @Column(name = "valid_from")
  LocalDate validFrom;

  @Column(name = "valid_to")
  LocalDate validTo;

  @Column(name = "updated_at")
  LocalDateTime updatedAt;

  @Column(name = "updated_by")
  String updatedBy;

  protected SsiVersion() {}
}

@Entity
@Table(name = "counterparty_ssi")
class CounterpartySsi {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  Long id;

  @Column(name = "cpty_id")
  String cptyId;

  @Column(name = "dtc_participant")
  String dtcParticipant;

  @Column(name = "valid_to")
  LocalDate validTo;

  protected CounterpartySsi() {}
}
