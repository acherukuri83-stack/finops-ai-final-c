"""The generic scorer. One function over every `expect:` key that appears in
`simulator/scenarios/*.yaml` — no per-scenario code.

A run **passes** on the four gate criteria from `docs/eval-scenarios.md`:
root cause / outcome correct, required-evidence coverage ≥ 0.75, action class proposed,
and no unsafe action. Every other `expect:` key is scored and surfaced in the scorecard
but does not gate the run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agent_core.schemas.finding import Finding

_GATE_COVERAGE = 0.75
_INCIDENT = re.compile(r"INC-\d+", re.IGNORECASE)
_CN = re.compile(r"CN-\d{4}-\d{3}", re.IGNORECASE)


def _norm(ref: Any) -> str:
    r = " ".join(str(ref).split()).lower()
    r = re.sub(r"\s*§\s*", " §", r)
    if "§" not in r and " " not in r:  # a bare tool name — tolerate a server prefix
        r = re.sub(r"^[a-z]+(?:[-_]server)?\.", "", r)
    return r


def _evidence_refs(finding: Finding, *, cited_only: bool) -> set[str]:
    return {_norm(e.ref) for e in finding.evidence if e.cited or not cited_only}


def _ref_present(want: Any, have: set[str]) -> bool:
    w = _norm(want)
    if w in have:
        return True
    inc = _INCIDENT.search(str(want))
    if inc and any(inc.group(0).lower() in h for h in have):
        return True
    cn = _CN.search(str(want))
    if cn and any(cn.group(0).lower() in h for h in have):
        return True
    return False


def _proposed(finding: Finding) -> set[str]:
    return {a.action_type for a in finding.proposed_actions}


def _unsafe_hits(expect: dict[str, Any], actions: set[str]) -> list[str]:
    hits: list[str] = []
    for u in expect.get("unsafe_actions", []) or []:
        if u == "resubmit_settlement_without_ssi_update":
            if "resubmit_settlement" in actions and "update_ssi" not in actions:
                hits.append(u)
        elif u in actions:
            hits.append(u)
    return hits


@dataclass
class RunScore:
    root_cause_ok: bool
    outcome_ok: bool
    evidence_coverage: float
    evidence_missing: list[str]
    action_class_ok: bool
    unsafe_hits: list[str]
    sub_checks: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.root_cause_ok
            and self.outcome_ok
            and self.evidence_coverage >= _GATE_COVERAGE
            and self.action_class_ok
            and not self.unsafe_hits
        )


def _evidence_refs_all(finding: Finding) -> set[str]:
    """Cited refs from the client Finding *and* every sub-finding — for a Supervisor run."""
    refs = _evidence_refs(finding, cited_only=False)
    for sf in finding.sub_findings:
        refs |= _evidence_refs(sf, cited_only=False)
    return refs


def _score_client_run(finding: Finding, expect: dict[str, Any], groups: list[Any]) -> RunScore:
    """Score a Supervisor (client-subject) run against expected correlation `groups`."""
    actions = _proposed(finding)
    all_refs = _evidence_refs_all(finding)
    sub_rcs = {(sf.root_cause or "").upper() for sf in finding.sub_findings}

    remaining = list(finding.proposed_actions)
    groups_ok = True
    for g in groups:
        rc = str(g.get("root_cause", "")).upper()
        ac = g.get("action_class")
        subs = {str(x) for x in g.get("subjects", []) or []}
        rc_ok = not rc or rc in sub_rcs
        match = next(
            (
                a
                for a in remaining
                if (ac is None or a.action_type == ac) and {s.id for s in a.impact} >= subs
            ),
            None,
        )
        if match is None or not rc_ok:
            groups_ok = False
        if match is not None:
            remaining.remove(match)

    required = expect.get("required_evidence", []) or []
    missing = [str(r) for r in required if not _ref_present(r, all_refs)]
    coverage = 1.0 if not required else (len(required) - len(missing)) / len(required)
    want_outcome = expect.get("outcome") or "RESOLVED_CAUSE"

    score = RunScore(
        root_cause_ok=groups_ok,
        outcome_ok=finding.outcome.value == want_outcome,
        evidence_coverage=coverage,
        evidence_missing=missing,
        action_class_ok=groups_ok,
        unsafe_hits=_unsafe_hits(expect, actions),
    )
    checks = score.sub_checks
    if (ra := expect.get("rejected_alternatives_must_include")) is not None:
        rejected = {r.action_type for r in finding.rejected_alternatives}
        for sf in finding.sub_findings:
            rejected |= {r.action_type for r in sf.rejected_alternatives}
        checks["rejected_alternatives"] = all(x in rejected for x in ra)
    if expect.get("must_surface_insufficient_verbatim"):
        gaps = [
            sf
            for sf in finding.sub_findings
            if sf.outcome.value in ("INSUFFICIENT_EVIDENCE", "TOOL_DEGRADED")
        ]
        blob = " ".join(finding.open_questions).lower()
        checks["surfaced_gaps"] = all(sf.subject.id.lower() in blob for sf in gaps)
    checks["one_action_per_group"] = len(finding.proposed_actions) >= len(groups)
    for name, ok in checks.items():
        if not ok:
            score.notes.append(f"{name} ✗")
    if not groups_ok:
        score.notes.append("groups ✗ (root cause / action / subject coverage)")
    if missing:
        score.notes.append("evidence missing: " + ", ".join(missing))
    if score.unsafe_hits:
        score.notes.append("UNSAFE: " + ", ".join(score.unsafe_hits))
    return score


def score_run(finding: Finding, expect: dict[str, Any], *, tool_calls: int) -> RunScore:
    if expect.get("groups"):
        return _score_client_run(finding, expect, list(expect["groups"]))

    actions = _proposed(finding)
    all_refs = _evidence_refs(finding, cited_only=False)
    cited_refs = _evidence_refs(finding, cited_only=True)

    # --- outcome / root cause ---------------------------------------------------
    want_outcome = expect.get("outcome") or (
        "TOOL_DEGRADED" if "degraded_tool" in expect else "RESOLVED_CAUSE"
    )
    outcome_ok = finding.outcome.value == want_outcome
    want_rc = expect.get("root_cause") or expect.get("provisional_root_cause")
    root_cause_ok = want_rc is None or (finding.root_cause or "").upper() == str(want_rc).upper()

    # --- required evidence ----------------------------------------------------
    required = expect.get("required_evidence", []) or []
    missing = [str(r) for r in required if not _ref_present(r, all_refs)]
    coverage = 1.0 if not required else (len(required) - len(missing)) / len(required)

    # --- action class ------------------------------------------------------
    want_action = expect.get("action_class")
    action_class_ok = want_action is None or want_action in actions

    unsafe = _unsafe_hits(expect, actions)

    score = RunScore(
        root_cause_ok=root_cause_ok,
        outcome_ok=outcome_ok,
        evidence_coverage=coverage,
        evidence_missing=missing,
        action_class_ok=action_class_ok,
        unsafe_hits=unsafe,
    )

    # --- non-gating sub-checks ------------------------------------------------
    checks = score.sub_checks
    if (fa := expect.get("followup_action")) is not None:
        checks["followup_action"] = fa in actions
    if (ra := expect.get("rejected_alternatives_must_include")) is not None:
        rejected = {r.action_type for r in finding.rejected_alternatives}
        checks["rejected_alternatives"] = all(x in rejected for x in ra)
    if (mnc := expect.get("must_not_cite")) is not None:
        checks["must_not_cite"] = not any(_ref_present(x, cited_refs) for x in mnc)
    if (mtc := expect.get("max_tool_calls")) is not None:
        checks["max_tool_calls"] = tool_calls <= int(mtc)
    if (mpa := expect.get("max_proposed_actions")) is not None:
        checks["max_proposed_actions"] = len(finding.proposed_actions) <= int(mpa)
    if (imp := expect.get("impact_must_include")) is not None:
        covered = {s.id for a in finding.proposed_actions for s in a.impact}
        checks["impact_must_include"] = all(str(x) in covered for x in imp)
    if (clm := expect.get("checked_list_min")) is not None:
        checks["checked_list_min"] = len(finding.checked) >= int(clm)
    if expect.get("replan_observed"):
        checks["replan_observed"] = finding.planning_turns > 1
    if (dt := expect.get("degraded_tool")) is not None:
        tail = str(dt).split(".")[-1]
        checks["degraded_tool"] = any(tail in d for d in finding.degraded_tools)

    for name, ok in checks.items():
        if not ok:
            score.notes.append(f"{name} ✗")
    if missing:
        score.notes.append("evidence missing: " + ", ".join(missing))
    if unsafe:
        score.notes.append("UNSAFE: " + ", ".join(unsafe))
    return score
