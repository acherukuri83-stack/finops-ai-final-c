-- Phase A schema: clients, accounts, SSIs, securities, market data, counterparties,
-- trades, settlement, positions, compliance, logs, incidents.
-- Plain REST + JPA tables; no business logic here (that lives in the simulator/agent tiers).

create table clients (
    client_id   varchar(64) primary key,
    name        varchar(200) not null,
    type        varchar(32) not null,
    status      varchar(32) not null
);

create table accounts (
    account_id  varchar(32) primary key,
    client_id   varchar(64) not null references clients(client_id),
    custodian   varchar(64) not null,
    status      varchar(32) not null
);
create index idx_accounts_client on accounts(client_id);

create table ssi_versions (
    id              bigserial primary key,
    account_id      varchar(32) not null references accounts(account_id),
    version         int not null,
    dtc_participant varchar(16) not null,
    agent_bic       varchar(16),
    valid_from      date not null,
    valid_to        date,
    updated_at      timestamp not null,
    updated_by      varchar(64) not null,
    unique (account_id, version)
);
create index idx_ssi_versions_account on ssi_versions(account_id);

create table securities (
    security_id   varchar(16) primary key,
    isin          varchar(24) not null,
    cusip         varchar(16) not null,
    description   varchar(200) not null,
    settle_cycle  varchar(8) not null,
    status        varchar(32) not null
);

create table market_calendar (
    market           varchar(16) not null,
    calendar_date    date not null,
    is_business_day  boolean not null,
    holiday_name     varchar(100),
    primary key (market, calendar_date)
);

create table prices (
    security_id  varchar(16) not null references securities(security_id),
    price_date   date not null,
    close_price  numeric(18,4) not null,
    primary key (security_id, price_date)
);

create table counterparties (
    cpty_id  varchar(16) primary key,
    name     varchar(200) not null,
    status   varchar(32) not null
);

create table counterparty_ssi (
    id              bigserial primary key,
    cpty_id         varchar(16) not null references counterparties(cpty_id),
    dtc_participant varchar(16) not null,
    valid_to        date
);
create index idx_cpty_ssi_cpty on counterparty_ssi(cpty_id);

create table trades (
    trade_id       varchar(16) primary key,
    client_id      varchar(64) not null references clients(client_id),
    account_id     varchar(32) not null references accounts(account_id),
    security_id    varchar(16) not null references securities(security_id),
    qty            bigint not null,
    side           varchar(8) not null,
    price          numeric(18,4) not null,
    trade_date     date not null,
    settle_date    date not null,
    status         varchar(32) not null,
    failure_code   varchar(64),
    cpty_id        varchar(16) not null references counterparties(cpty_id),
    booked_at      timestamp not null
);
create index idx_trades_client on trades(client_id);
create index idx_trades_account on trades(account_id);
create index idx_trades_status on trades(status);
create index idx_trades_security on trades(security_id);
create index idx_trades_trade_date on trades(trade_date);
create index idx_trades_settle_date on trades(settle_date);

create table settlement_attempts (
    id         bigserial primary key,
    trade_id   varchar(16) not null references trades(trade_id) on delete cascade,
    at         timestamp not null,
    result     varchar(32) not null,
    detail     varchar(500)
);
create index idx_settlement_attempts_trade on settlement_attempts(trade_id);

create table affirmations (
    id            bigserial primary key,
    trade_id      varchar(16) not null references trades(trade_id) on delete cascade,
    cpty_id       varchar(16) not null references counterparties(cpty_id),
    cpty_dtc      varchar(16) not null,
    affirmed      boolean not null,
    affirmed_at   timestamp
);
create index idx_affirmations_trade on affirmations(trade_id);

create table positions (
    account_id       varchar(32) not null references accounts(account_id),
    security_id      varchar(16) not null references securities(security_id),
    as_of            date not null,
    qty              bigint not null,
    available        bigint not null,
    pending_deliver  bigint not null default 0,
    pending_receive  bigint not null default 0,
    primary key (account_id, security_id, as_of)
);

create table borrow_availability (
    security_id    varchar(16) primary key references securities(security_id),
    available_qty  bigint not null,
    rate           numeric(8,4) not null,
    recalls        jsonb not null default '[]'
);

create table restrictions (
    id        bigserial primary key,
    account_id varchar(32) not null references accounts(account_id),
    type      varchar(32) not null,
    reason    varchar(200) not null,
    set_by    varchar(64) not null,
    set_at    timestamp not null,
    active    boolean not null default true
);
create index idx_restrictions_account on restrictions(account_id);

create table screening_results (
    client_id   varchar(64) primary key references clients(client_id),
    status      varchar(32) not null,
    checked_at  timestamp not null
);

create table app_logs (
    id        bigserial primary key,
    ts        timestamp not null,
    svc       varchar(64) not null,
    level     varchar(16) not null,
    msg       varchar(500) not null,
    trade_id  varchar(16)
);
create index idx_app_logs_trade on app_logs(trade_id);
create index idx_app_logs_ts on app_logs(ts);
create index idx_app_logs_svc on app_logs(svc);

-- Metadata only — incident narrative text lives in ai-platform/knowledge (W2 corpus).
create table incidents (
    incident_id  varchar(16) primary key,
    occurred_at  timestamp not null,
    status       varchar(32) not null default 'CLOSED'
);
