# Tool Contracts — Phase A

Every MCP tool declares `access: read | write`. Write tools take `approval_id` and validate it against `case.get_approval` **inside the tool** before doing anything; a missing, unknown, PENDING, or REJECTED id returns `ApprovalError`, never executes. All tools return the common error envelope on failure.

```
ErrorEnvelope { code: str, message: str, retryable: bool, tool: str }
```

Ids: `trade_id` (T######), `account_id` (ACC-#####), `client_id` (UPPER_SNAKE), `cpty_id` (CP-###), `security_id` (ticker for Phase A), `case_id` (CS-####), `approval_id` (ap_xxxx). Tools never accept a client_id where an account_id is expected — the description says which.

Descriptions below are the exact text exposed to the model. They say when to use the tool and when not to.

---

## trade-server

| Tool | Access | Signature | Description (as exposed) |
|---|---|---|---|
| `get_trade` | read | `(trade_id) → Trade` | Full trade record: client, account, security, qty, side, dates, status, counterparty. Use first for any trade question. |
| `get_settlement_status` | read | `(trade_id) → SettlementStatus` | Settlement state, failure_code, failure_detail, attempts[] with timestamps. Use to learn *why* a trade is not settled. Returns failure_code=null if never attempted. |
| `find_trades` | read | `(client_id?, account_id?, status?, security_id?, trade_date?, settle_date?) → TradeSummary[]` | Search trades by filters. Use to find related trades (same client, same security, same day) e.g. for duplicates or blast radius. Do not use to fetch a known trade_id — use get_trade. |
| `resubmit_settlement` | **write** | `(trade_id, approval_id) → Submission` | Resubmit a failed trade for settlement using current instructions. Requires an APPROVED approval_id. Does not change any SSI. |
| `cancel_trade` | **write** | `(trade_id, reason, approval_id) → CancelResult` | Cancel a trade (e.g. a duplicate booking). Requires an APPROVED approval_id. Irreversible. |

```
Trade { trade_id, client_id, account_id, security_id, qty, side, price, trade_date, settle_date, status, cpty_id, booked_at }
SettlementStatus { trade_id, status, failure_code?, failure_detail?, attempts: [{at, result, detail}], last_attempt_at? }
```

## client-server

| Tool | Access | Signature | Description |
|---|---|---|---|
| `get_client` | read | `(client_id) → Client` | Client name, type, status, restrictions[]. Use for client-level restrictions. |
| `get_account` | read | `(account_id) → Account` | Account custodian, status, restrictions[], risk_flags[]. Use to check whether an account can settle. Takes account_id, not client_id. |
| `get_ssi` | read | `(account_id, security_type?) → SSI` | The **current** standing settlement instruction for an account (dtc_participant, agent_bic, valid_from, valid_to, updated_at, updated_by). Use for the current value only. |
| `get_ssi_history` | read | `(account_id) → SSIVersion[]` | All SSI versions with effective ranges and who changed them. Use when the SSI may have changed recently or when comparing our instruction against a counterparty's. |
| `update_ssi` | **write** | `(account_id, dtc_participant, valid_from, approval_id) → SSIVersion` | Replace the account's current SSI. Requires an APPROVED approval_id. Only appropriate when *our* instruction is confirmed wrong; a counterparty mismatch alone is not grounds. |

## counterparty-server

| Tool | Access | Signature | Description |
|---|---|---|---|
| `get_counterparty` | read | `(cpty_id) → Counterparty` | Counterparty name, status, contacts. |
| `get_counterparty_ssi` | read | `(cpty_id) → CptySSI` | The instruction the counterparty has on file for us, with valid_to. Use to check expiry. |
| `get_affirmation` | read | `(trade_id) → Affirmation` | Whether and how the counterparty affirmed the trade: affirmed, cpty_dtc, affirmed_at. Compare cpty_dtc with our current SSI to detect mismatch. |

## position-server

| Tool | Access | Signature | Description |
|---|---|---|---|
| `get_position` | read | `(account_id, security_id, as_of?) → Position` | qty, available, pending_deliver, pending_receive. Use for delivery shortfalls. |
| `get_borrow_availability` | read | `(security_id) → BorrowAvailability` | available_qty, rate, recalls[]. Use only after a shortfall is confirmed. |

## reference-server

| Tool | Access | Signature | Description |
|---|---|---|---|
| `get_security` | read | `(security_id) → Security` | isin, cusip, ticker, description, settle_cycle, status. Use to validate identifiers when a reference-data problem is suspected. |
| `get_market_calendar` | read | `(date, market) → CalendarDay` | is_business_day, holiday?. Use when a settle_date looks wrong. |

## market-server

| Tool | Access | Signature | Description |
|---|---|---|---|
| `get_price` | read | `(security_id, as_of?) → Price` | Close/last price. Realism only in Phase A; rarely needed for settlement investigations. |

## compliance-server (read-only in Phase A)

| Tool | Access | Signature | Description |
|---|---|---|---|
| `get_restrictions` | read | `(account_id) → Restriction[]` | Active restrictions with reason, set_by, set_at. A settlement restriction means the trade cannot settle regardless of SSI. |
| `get_screening_result` | read | `(client_id) → Screening` | Latest sanctions screening status. Phase A data is always CLEAR. |

## ops-server

| Tool | Access | Signature | Description |
|---|---|---|---|
| `search_logs` | read | `(query, trade_id?, system?, from?, to?) → LogEntry[]` | Application logs across simulated services. Use with trade_id to find corroborating errors. Returns newest first, max 50. |
| `search_knowledge` | read | `(query, k=5) → Chunk[]` | Operating procedures and policies, section-level. Returns {doc, section, title, text, score}. Cite as "doc §section". Use after the failure code is known. |
| `find_incidents` | read | `(query, k=3) → Incident[]` | Historical incidents {incident_id, summary, root_cause, resolution, similarity}. |

## case-server

| Tool | Access | Signature | Description |
|---|---|---|---|
| `create_case` | write* | `(subject_type, subject_id, summary, evidence[]) → Case` | Open a case for a subject. *Agent-allowed without approval — it is bookkeeping. |
| `update_case` | write* | `(case_id, notes, status?) → Case` | Append notes / change status. |
| `propose_action` | write* | `(case_id, action_type, params, rationale, impact[]) → Approval` | Register a proposed action; returns approval_id with status PENDING. The only way an agent can request a write. |
| `get_approval` | read | `(approval_id) → Approval` | status PENDING/APPROVED/REJECTED, decided_by, role, decided_at. Write tools call this. |
| `log_audit` | write* | `(case_id, event) → AuditEvent` | Append an audit event. |

`propose_action` validates `action_type` against the calling agent's allowlist (`agent_core/policy/allowlists.yaml`) and returns `PolicyError` on violation.

---

## Phase A allowlist

```yaml
investigator:
  - resubmit_settlement
  - cancel_trade
  - update_ssi
  - open_compliance_referral   # case-server action, no target tool in Phase A
  - escalate                   # case-server action
```
