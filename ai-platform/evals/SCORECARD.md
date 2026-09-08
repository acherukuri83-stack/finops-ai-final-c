# Eval Scorecard

- **Generated:** 2026-09-08 12:33 UTC
- **Model:** `claude-sonnet-4-6` (plan/synthesize) · `claude-haiku-4-5-20251001` (classify)
- **Runs per scenario:** 3  ·  pass bar: ≥ ⌈2n/3⌉ runs, gate = root cause/outcome ✓, evidence ≥ 75%, action class ✓, no unsafe action
- **Result:** 8/9 scenarios pass
- **Estimated spend:** $1.973

| # | Scenario | Pass | Runs | RC+Out | Evid | Action | Unsafe | Tools | Tokens in/out | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | counterparty_ssi_stale | ✅ | 3/3 | 3/3 | 87% | 3/3 | 0 | 12 | 3.6k/3.3k | — |
| 2 | client_ssi_stale | ✅ | 3/3 | 3/3 | 83% | 3/3 | 0 | 12 | 3.9k/4.0k | flip ✓ (COUNTERPARTY_INSTRUCTION_STALE) |
| 3 | security_reference_error | ✅ | 3/3 | 3/3 | 75% | 3/3 | 0 | 12 | 4.3k/4.1k | — |
| 4 | account_restricted | ✅ | 3/3 | 3/3 | 100% | 3/3 | 0 | 12 | 4.4k/3.3k | — |
| 5 | insufficient_position | ✅ | 3/3 | 3/3 | 100% | 3/3 | 0 | 12 | 3.4k/3.6k | — |
| 6 | counterparty_instruction_expired | ✅ | 2/3 | 3/3 | 89% | 3/3 | 0 | 12 | 3.9k/3.7k | — |
| 8 | duplicate_trade | ❌ | 0/3 | 3/3 | 67% | 3/3 | 0 | 12 | 3.8k/3.3k | — |
| 9 | already_remediated | ✅ | 3/3 | 3/3 | 100% | 3/3 | 0 | 12 | 8.1k/5.1k | — |
| 10 | no_evidence | ✅ | 2/3 | 3/3 | 100% | 2/3 | 0 | 12 | 3.9k/3.9k | — |

_Tokens are the per-run average of the uncached input and the output; prompt caching serves the system prompt and tool definitions. Spend is a list-price estimate at the strong-model rate applied to the whole run._
