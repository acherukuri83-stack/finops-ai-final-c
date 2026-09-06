package finops.enterprise;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** `counterparties` — see V2__phase_a_schema.sql. */
@Entity
@Table(name = "counterparties")
class Counterparty {
  @Id
  @Column(name = "cpty_id")
  String cptyId;

  String name;
  String status;

  protected Counterparty() {}
}
