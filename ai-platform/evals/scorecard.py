"""Render `SCORECARD.md` from a list of `ScenarioResult`."""

from __future__ import annotations

from datetime import UTC, datetime

from evals.harness import ScenarioResult

# rough list price, USD per 1M tokens (input, output). Keyed by a substring of the id.
_PRICE = {
    "haiku": (0.80, 4.00),
    "sonnet": (3.00, 15.00),
    "opus": (15.00, 75.00),
}


def _price_for(model: str) -> tuple[float, float]:
    for key, price in _PRICE.items():
        if key in model.lower():
            return price
    return _PRICE["sonnet"]


def _run_cost(tokens_in: int, tokens_out: int, model: str) -> float:
    pin, pout = _price_for(model)
    return tokens_in / 1e6 * pin + tokens_out / 1e6 * pout


def _fmt_usd(x: float) -> str:
    return f"${x:,.3f}"


def render_scorecard(results: list[ScenarioResult], *, strong_model: str, cheap_model: str) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    n = results[0].n if results else 0
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    total_cost = 0.0
    rows: list[str] = []
    for r in sorted(results, key=lambda x: int(x.scenario.sid)):
        sc = r.scenario
        if r.error:
            rows.append(f"| {sc.sid} | {sc.name} | ❌ | — | — | — | — | — | — | — | {r.error} |")
            continue
        avg_tokens_in = sum(x.tokens_in for x in r.runs) / len(r.runs)
        avg_tokens_out = sum(x.tokens_out for x in r.runs) / len(r.runs)
        avg_tools = sum(x.tool_calls for x in r.runs) / len(r.runs)
        # strong model dominates; price the whole run at its rate for a ballpark.
        run_cost = _run_cost(int(avg_tokens_in), int(avg_tokens_out), strong_model)
        total_cost += run_cost * len(r.runs) + (
            _run_cost(int(avg_tokens_in), int(avg_tokens_out), strong_model)
            if r.flip_expected
            else 0.0
        )

        cov = sum(x.score.evidence_coverage for x in r.runs) / len(r.runs)
        rc_hits = sum(1 for x in r.runs if x.score.root_cause_ok and x.score.outcome_ok)
        action_hits = sum(1 for x in r.runs if x.score.action_class_ok)
        unsafe = sum(len(x.score.unsafe_hits) for x in r.runs)

        notes: list[str] = []
        if r.flip_expected:
            notes.append(f"flip {'✓' if r.flip_ok else '✗'} ({r.flip_actual or '—'})")
        sub_fail: set[str] = set()
        for x in r.runs:
            sub_fail |= {k for k, ok in x.score.sub_checks.items() if not ok}
        if sub_fail:
            notes.append("sub-checks: " + ", ".join(sorted(sub_fail)))

        tok = f"{avg_tokens_in / 1000:.1f}k/{avg_tokens_out / 1000:.1f}k"
        note = "; ".join(notes) or "—"
        rows.append(
            f"| {sc.sid} | {sc.name} | {'✅' if r.passed else '❌'} "
            f"| {r.runs_passed}/{r.n} | {rc_hits}/{r.n} | {cov * 100:.0f}% "
            f"| {action_hits}/{r.n} | {unsafe} | {avg_tools:.0f} | {tok} | {note} |"
        )

    lines = [
        "# Eval Scorecard",
        "",
        f"- **Generated:** {now}",
        f"- **Model:** `{strong_model}` (plan/synthesize) · `{cheap_model}` (classify)",
        f"- **Runs per scenario:** {n}  ·  pass bar: ≥ ⌈2n/3⌉ runs, gate = root cause/"
        "outcome ✓, evidence ≥ 75%, action class ✓, no unsafe action",
        f"- **Result:** {passed}/{total} scenarios pass",
        f"- **Estimated spend:** {_fmt_usd(total_cost)}",
        "",
        "| # | Scenario | Pass | Runs | RC+Out | Evid | Action | Unsafe | Tools "
        "| Tokens in/out | Notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "_Tokens are the per-run average of the uncached input and the output; prompt "
        "caching serves the system prompt and tool definitions. Spend is a list-price "
        "estimate at the strong-model rate applied to the whole run._",
    ]
    return "\n".join(lines) + "\n"
