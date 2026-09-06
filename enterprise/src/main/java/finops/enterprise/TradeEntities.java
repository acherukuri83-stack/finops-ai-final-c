package finops.enterprise;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/** `trades`, `settlement_attempts`, `affirmations` — see V2__phase_a_schema.sql. */
@Entity
@Table(name = "trades")
class Trade {
  @Id
  @Column(name = "trade_id")
  String tradeId;

  @Column(name = "client_id")
  String clientId;

  @Column(name = "account_id")
  String accountId;

  @Column(name = "security_id")
  String securityId;

  Long qty;
  String side;
  BigDecimal price;

  @Column(name = "trade_date")
  LocalDate tradeDate;

  @Column(name = "settle_date")
  LocalDate settleDate;

  String status;

  @Column(name = "failure_code")
  String failureCode;

  @Column(name = "cpty_id")
  String cptyId;

  @Column(name = "booked_at")
  LocalDateTime bookedAt;

  protected Trade() {}
}

@Entity
@Table(name = "settlement_attempts")
class SettlementAttempt {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  Long id;

  @Column(name = "trade_id")
  String tradeId;

  LocalDateTime at;
  String result;
  String detail;

  protected SettlementAttempt() {}
}

@Entity
@Table(name = "affirmations")
class Affirmation {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  Long id;

  @Column(name = "trade_id")
  String tradeId;

  @Column(name = "cpty_id")
  String cptyId;

  @Column(name = "cpty_dtc")
  String cptyDtc;

  Boolean affirmed;

  @Column(name = "affirmed_at")
  LocalDateTime affirmedAt;

  protected Affirmation() {}
}
