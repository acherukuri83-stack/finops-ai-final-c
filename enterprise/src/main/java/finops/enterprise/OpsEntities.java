package finops.enterprise;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/** `app_logs`, `incidents` — see V2__phase_a_schema.sql. */
@Entity
@Table(name = "app_logs")
class AppLog {
  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  Long id;

  LocalDateTime ts;
  String svc;
  String level;
  String msg;

  @Column(name = "trade_id")
  String tradeId;

  protected AppLog() {}
}

@Entity
@Table(name = "incidents")
class Incident {
  @Id
  @Column(name = "incident_id")
  String incidentId;

  @Column(name = "occurred_at")
  LocalDateTime occurredAt;

  String status;

  protected Incident() {}
}
