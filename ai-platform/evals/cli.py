"""`python -m evals.cli [--scenario N] [--n 3] [--out SCORECARD.md]`

Runs the Investigator against the scenario suite with a real model, scores each run
against the scenario's `expect:` block, writes `SCORECARD.md`, and exits non-zero if any
scenario fails its pass bar. Costs real money — see `docs/eval-scenarios.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from agent_core.reasoning.model_client import AnthropicModelClient
from agent_core.reasoning.model_router import Step, model_for
from evals.harness import ScenarioResult, all_scenarios, load_scenario, run_scenario
from evals.metrics import CountingModelClient, install_span_sink
from evals.scorecard import render_scorecard
from platform_api import cases
from platform_api.settings import settings


async def _run(scenario: str | None, n: int) -> list[ScenarioResult]:
    scenarios = [load_scenario(scenario)] if scenario else all_scenarios()
    if not settings.anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set — the eval suite needs a real model.")
    counter = CountingModelClient(AnthropicModelClient(settings.anthropic_api_key))
    cases.set_backend(cases.MemBackend())  # score the Finding, not a case DB
    results: list[ScenarioResult] = []
    for sc in scenarios:
        print(f"[eval] scenario {sc.sid} ({sc.name}) — {n} run(s)…", flush=True)
        res = await run_scenario(sc, n=n, counter=counter)
        state = "PASS" if res.passed else "FAIL"
        detail = res.error or f"{res.runs_passed}/{res.n} runs"
        print(f"[eval] scenario {sc.sid}: {state} — {detail}", flush=True)
        results.append(res)
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", help="a single scenario id (default: the whole suite)")
    ap.add_argument("--n", type=int, default=3, help="runs per scenario (default 3)")
    ap.add_argument("--out", default="evals/SCORECARD.md", help="scorecard path")
    args = ap.parse_args()

    # the scorecard has ✓ / ≥ / em-dashes; don't die echoing it on a cp1252 console
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    install_span_sink()
    results = asyncio.run(_run(args.scenario, args.n))

    md = render_scorecard(
        results,
        strong_model=model_for(Step.SYNTHESIZE),
        cheap_model=model_for(Step.CLASSIFY),
    )
    Path(args.out).write_text(md, encoding="utf-8")
    print("\n" + md)

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"FAILED: {', '.join(r.scenario.sid for r in failed)}")
        sys.exit(1)
    print("all scenarios passed")


if __name__ == "__main__":
    main()
