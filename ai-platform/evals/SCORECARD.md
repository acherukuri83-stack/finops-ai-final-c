# Eval Scorecard

- **Generated:** 2026-09-08 11:43 UTC
- **Model:** `claude-sonnet-4-6` (plan/synthesize) · `claude-haiku-4-5-20251001` (classify)
- **Runs per scenario:** 3  ·  pass bar: ≥ ⌈2n/3⌉ runs, gate = root cause/outcome ✓, evidence ≥ 75%, action class ✓, no unsafe action
- **Result:** 8/9 scenarios pass
- **Estimated spend:** $2.188

| # | Scenario | Pass | Runs | RC+Out | Evid | Action | Unsafe | Tools | Tokens in/out | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | counterparty_ssi_stale | ✅ | 3/3 | 3/3 | 87% | 3/3 | 0 | 12 | 5.7k/4.3k | — |
| 2 | client_ssi_stale | ✅ | 3/3 | 3/3 | 75% | 3/3 | 0 | 12 | 4.6k/4.3k | flip ✓ (COUNTERPARTY_INSTRUCTION_STALE) |
| 3 | security_reference_error | ✅ | 3/3 | 3/3 | 75% | 3/3 | 0 | 12 | 4.6k/4.5k | — |
| 4 | account_restricted | ✅ | 3/3 | 3/3 | 100% | 3/3 | 0 | 12 | 5.9k/3.9k | — |
| 5 | insufficient_position | ✅ | 3/3 | 3/3 | 100% | 3/3 | 0 | 12 | 3.1k/3.5k | — |
| 6 | counterparty_instruction_expired | ✅ | 3/3 | 3/3 | 100% | 3/3 | 0 | 12 | 5.2k/4.5k | — |
| 8 | duplicate_trade | ❌ | 1/3 | 3/3 | 67% | 3/3 | 0 | 12 | 4.4k/3.4k | — |
| 9 | already_remediated | ✅ | 3/3 | 3/3 | 100% | 3/3 | 0 | 12 | 6.3k/4.6k | — |
| 10 | no_evidence | ✅ | 3/3 | 3/3 | 100% | 3/3 | 0 | 12 | 5.2k/4.9k | — |

_Tokens are the per-run average (input includes cached-prompt reads). Spend is a list-price estimate, strong-model rate applied to the whole run._
