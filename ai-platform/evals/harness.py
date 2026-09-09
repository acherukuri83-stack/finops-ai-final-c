"""The eval harness: seed a scenario, run the Investigator n times, score each run
against the scenario's own `expect:` block, aggregate.

Seeding shells out to the simulator (its own uv project) and ingests the corpus in
process. A scenario's fixtures are inferred from its `required_evidence` — any
`CN-YYYY-NNN` token names a corpus fixture. `flip_test` scenarios also run once with
those fixtures removed.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from typing import Any

import yaml

from agent_core.loop import investigate
from agent_core.schemas.finding import Finding
from agent_core.supervisor import investigate_client
from agent_core.wire import investigate_wire
from evals.metrics import CountingModelClient, span_sink
from evals.scoring import RunScore, score_run

_REPO = Path(__file__).resolve().parents[2]
_SCENARIO_DIR = _REPO / "simulator" / "scenarios"
_SIMULATOR = _REPO / "simulator"
_CN = re.compile(r"CN-\d{4}-\d{3}")

# Sc. 12 needs process-global FAULT_INJECT on the enterprise; covered by tests/test_loop.py.
SKIP_BY_DEFAULT = {"12"}


@dataclass(frozen=True)
class Scenario:
    sid: str
    name: str
    path: Path
    trade_id: str
    expect: dict[str, Any]
    fixtures: frozenset[str]
    subject_kind: str = "trade"  # "trade" | "client" (Supervisor fan-out) | "wire" (Phase B)
    subject_id: str = ""  # the client id for "client"; the wire id for "wire"

    @staticmethod
    def load(path: Path) -> Scenario:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        plant = raw.get("plant") or {}
        trades = plant.get("trades") or []
        failed = [t for t in trades if t.get("status") == "FAILED"]
        first = (failed or trades)[0] if trades else {}
        trade_id = str(first.get("id", "")) if trades else ""
        expect = raw.get("expect") or {}
        subject = expect.get("subject")
        subject_kind = subject if subject in ("client", "wire") else "trade"
        if subject_kind == "client":
            subject_id = str(first.get("client", ""))
        elif subject_kind == "wire":
            subject_id = str((plant.get("wires") or [{}])[0].get("id", ""))
        else:
            subject_id = trade_id
        fixtures = {
            m for ref in expect.get("required_evidence", []) or [] for m in _CN.findall(str(ref))
        }
        return Scenario(
            sid=str(raw.get("id", path.stem.split("_")[0].lstrip("0"))),
            name=str(raw.get("name", "")),
            path=path,
            trade_id=trade_id,
            expect=expect,
            fixtures=frozenset(fixtures),
            subject_kind=subject_kind,
            subject_id=subject_id,
        )


def all_scenarios(*, include_skipped: bool = False) -> list[Scenario]:
    out = [Scenario.load(p) for p in sorted(_SCENARIO_DIR.glob("*.yaml"))]
    if include_skipped:
        return out
    return [s for s in out if s.sid not in SKIP_BY_DEFAULT]


def load_scenario(sid: str) -> Scenario:
    for s in all_scenarios(include_skipped=True):
        if s.sid == str(sid):
            return s
    raise KeyError(f"no scenario {sid}")


def _seed(sid: str, fixtures: frozenset[str]) -> None:
    from knowledge import ingest as knowledge_ingest

    subprocess.run(
        ["uv", "run", "python", "-m", "simulator.cli", "seed", "--scenario", sid],
        cwd=_SIMULATOR,
        check=True,
        capture_output=True,
        text=True,
    )
    knowledge_ingest.ingest(set(fixtures))


@dataclass
class RunResult:
    finding: Finding
    score: RunScore
    tool_calls: int
    model_calls: int
    tokens_in: int
    tokens_out: int
    cache_read: int


@dataclass
class ScenarioResult:
    scenario: Scenario
    n: int
    runs: list[RunResult] = field(default_factory=list)
    flip_expected: str | None = None
    flip_actual: str | None = None
    error: str | None = None

    @property
    def runs_passed(self) -> int:
        return sum(1 for r in self.runs if r.score.passed)

    @property
    def flip_ok(self) -> bool | None:
        if self.flip_expected is None:
            return None
        return (self.flip_actual or "").upper() == self.flip_expected.upper()

    @property
    def passed(self) -> bool:
        if self.error or not self.runs:
            return False
        need = ceil(2 * self.n / 3)  # 2/3, 2/2, 1/1
        return self.runs_passed >= need and self.flip_ok is not False


async def _run_subject(sc: Scenario, counter: CountingModelClient) -> Finding:
    """Dispatch to the single-trade path, the Supervisor, or the Wire specialist."""
    if sc.subject_kind == "client":
        return await investigate_client(sc.subject_id, client=counter, scenario_id=sc.sid)
    if sc.subject_kind == "wire":
        return await investigate_wire(sc.subject_id, client=counter, scenario_id=sc.sid)
    return await investigate(sc.trade_id, client=counter, scenario_id=sc.sid)


async def run_scenario(sc: Scenario, *, n: int, counter: CountingModelClient) -> ScenarioResult:
    result = ScenarioResult(scenario=sc, n=n)
    try:
        _seed(sc.sid, sc.fixtures)
    except subprocess.CalledProcessError as exc:
        result.error = f"seed failed: {(exc.stderr or exc.stdout or '').strip()[-400:]}"
        return result

    for _ in range(n):
        counter.reset()
        try:
            with span_sink() as sink:
                finding = await _run_subject(sc, counter)
            metrics = sink.read(counter)
        except Exception as exc:  # noqa: BLE001 — one bad run must not sink the suite
            result.error = f"run raised: {type(exc).__name__}: {exc}"
            return result
        score = score_run(finding, sc.expect, tool_calls=metrics.tool_calls)
        result.runs.append(
            RunResult(
                finding=finding,
                score=score,
                tool_calls=metrics.tool_calls,
                model_calls=metrics.model_calls,
                tokens_in=metrics.tokens_in,
                tokens_out=metrics.tokens_out,
                cache_read=metrics.cache_read,
            )
        )

    flip = sc.expect.get("flip_test")
    if isinstance(flip, dict) and flip.get("without_fixture_root_cause"):
        result.flip_expected = str(flip["without_fixture_root_cause"])
        try:
            _seed(sc.sid, frozenset())
            counter.reset()
            with span_sink():
                flip_finding = await investigate(sc.trade_id, client=counter, scenario_id=sc.sid)
            result.flip_actual = flip_finding.root_cause or ""
        except Exception as exc:  # noqa: BLE001
            result.error = f"flip run failed: {type(exc).__name__}: {exc}"
        finally:
            _seed(sc.sid, sc.fixtures)

    return result
