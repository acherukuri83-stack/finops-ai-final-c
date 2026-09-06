package finops.enterprise;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** `clients` and `accounts` — see V2__phase_a_schema.sql. */
@Entity
@Table(name = "clients")
class Client {
  @Id
  @Column(name = "client_id")
  String clientId;

  String name;
  String type;
  String status;

  protected Client() {}
}

@Entity
@Table(name = "accounts")
class Account {
  @Id
  @Column(name = "account_id")
  String accountId;

  @Column(name = "client_id")
  String clientId;

  String custodian;
  String status;

  protected Account() {}
}
