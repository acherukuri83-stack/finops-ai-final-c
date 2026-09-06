package finops.enterprise;

import jakarta.persistence.Column;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Embeddable;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Objects;

/** `positions`, `restrictions`, `screening_results` — see V2__phase_a_schema.sql. */
@Embeddable
class PositionId implements Serializable {
  @Column(name = "account_id")
  String accountId;

  @Column(name = "security_id")
  String securityId;

  @Column(name = "as_of")
  LocalDate asOf;

  protected PositionId() {}

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof PositionId that)) return false;
    return Objects.equals(accountId, that.accountId)
        && Objects.equals(securityId, that.securityId)
        && Objects.equals(asOf, that.asOf);
  }

  @Override
  public int hashCode() {
    return Objects.hash(accountId, securityId, asOf);
  }
}

@Entity
@Table(name = "positions")
class Position {
  @EmbeddedId PositionId id;

  Long qty;
  Long available;

  @Column(name = "pending_deliver")
  Long pendingDeliver;

  @Column(name = "pending_receive")
  Long pendingReceive;

  protected Position() {}
}

@Entity
@Table(name = "restrictions")
class Restriction {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  Long id;

  @Column(name = "account_id")
  String accountId;

  String type;
  String reason;

  @Column(name = "set_by")
  String setBy;

  @Column(name = "set_at")
  LocalDateTime setAt;

  Boolean active;

  protected Restriction() {}
}

@Entity
@Table(name = "screening_results")
class ScreeningResult {
  @Id
  @Column(name = "client_id")
  String clientId;

  String status;

  @Column(name = "checked_at")
  LocalDateTime checkedAt;

  protected ScreeningResult() {}
}
