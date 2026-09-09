"""The Developer Agent — PR-review mode (Phase E).

`review_pr(pr_id)` classifies the touched surfaces, runs the deterministic checks
(`ci` server), applies the platform-specific **hard rules in code**, cites the relevant
standard §, and returns a structured `Review`. The model-interpretation / prioritisation
layer (agent-plan Phase 12) is a follow-up — this slice is fully deterministic.

Hard rules (`docs/standards/security.md`):
- a write-shaped tool with no `approval_id` / `check_approval` → **BLOCKER** (§4.1)
- a new `action_type` not on any allowlist → **MAJOR** (§5)
- a model call on an un-scrubbed PII-shaped field → **BLOCKER** (§7)
- an `authored_by: agent` scenario → **MAJOR**, forces `REQUEST_CHANGES` (agent-plan: an
  agent-authored scenario cannot merge without a human reviewer)

Allowlist: `post_review`, `open_pull_request` (draft). **No `approve_pr` / `merge_pr`.**
"""

from __future__ import annotations

import re
from pathlib import Path

from agent_core.policy.engine import _allowlists
from agent_core.schemas.review import Review, ReviewFinding
from agent_core.spans import set_attrs, span
from mcp_servers.ci import store as ci_store
from mcp_servers.repo import store as repo_store

_STANDARDS = Path(__file__).resolve().parents[1].parent / "docs" / "standards"

_SURFACE_RULES: list[tuple[str, str]] = [
    ("mcp_contract", r"mcp_servers/.+/tools/"),
    ("agent_policy", r"agent_core/policy/"),
    ("prompt", r"agent_core/prompts/"),
    ("schema", r"agent_core/schemas/"),
    ("ui", r"portal/src/"),
    ("simulator", r"simulator/"),
    ("eval", r"(evals/|scenarios/.+\.yaml)"),
]

_SURFACE_STANDARD = {
    "mcp_contract": "security.md §2–§4 (write tools validate approval_id)",
    "agent_policy": "security.md §5 (proposals pass the allowlist)",
    "schema": "coding.md §2 (Pydantic for every schema)",
    "prompt": "coding.md §5 (prompts in prompts/**/*.md, never inlined)",
    "ui": "coding.md §20–§21 (TS strict; client from OpenAPI)",
    "eval": "coding.md §8 (scenario tests are real model calls, marked eval)",
}


async def review_pr(pr_id: str) -> Review:
    with span("review_pr", "agent", agent="developer", step="review") as root:
        pr = repo_store.get_pull_request(pr_id)
        if pr is None:
            review = Review(pr_id=pr_id, recommendation="COMMENT", summary=f"no PR {pr_id}")
            set_attrs(root, {"outcome": "OUT_OF_SCOPE"})
            return review

        diff = pr.get("diff") or ""
        files = list(pr.get("files") or [])
        surfaces = _classify(files, diff)
        findings: list[ReviewFinding] = []

        findings += _code_rules(files, diff)
        findings += _deterministic(pr_id)
        findings += _eval_impact(pr_id, files)

        rec = _recommend(findings)
        summary = _summary(surfaces, findings, rec)
        review = Review(
            pr_id=pr_id, surfaces=surfaces, findings=findings, recommendation=rec, summary=summary
        )
        set_attrs(
            root,
            {
                "review.recommendation": rec,
                "review.blockers": sum(f.severity == "BLOCKER" for f in findings),
                "surfaces": surfaces,
            },
        )
    return review


# --- classification --------------------------------------------------------------


def _classify(files: list[str], diff: str) -> list[str]:
    out: set[str] = set()
    for f in files:
        for name, pat in _SURFACE_RULES:
            if re.search(pat, f):
                out.add(name)
    if not out:
        out.add("other")
    return sorted(out)


# --- hard rules in code --------------------------------------------------------


def _added_lines(diff: str) -> list[str]:
    return [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


_WRITE_HINT = re.compile(
    r"(post_json|put_json|delete_json|record_action|add_change_ticket|\.insert\()"
)
_PII_VAR = re.compile(r"\b\w*(email|ssn|passport|dob|full_name)\w*\b", re.IGNORECASE)


def _file_for(diff: str) -> str:
    m = re.search(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)
    return m.group(1) if m else "?"


def _code_rules(files: list[str], diff: str) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    added = _added_lines(diff)
    joined = "\n".join(added)
    target = _file_for(diff)

    # §4.1 — a new write-shaped tool with no approval gate
    if re.search(r"mcp_servers/.+/tools/", target) and re.search(r"async def \w+\(", joined):
        if (
            _WRITE_HINT.search(joined)
            and "approval_id" not in joined
            and "check_approval" not in joined
        ):
            fn = re.search(r"async def (\w+)\(", joined)
            out.append(
                ReviewFinding(
                    severity="BLOCKER",
                    file=target,
                    line=_first_added_line(diff),
                    message=(
                        f"new tool `{fn.group(1) if fn else '?'}` mutates state with no "
                        f"`approval_id` parameter and no `check_approval` call"
                    ),
                    evidence=(
                        "security.md §4.1 — a write tool that can execute "
                        "without §2–§3 is a BLOCKER"
                    ),
                    suggested_patch=(
                        "add `approval_id: str` and a `check_approval(...)` "
                        "guard before the side effect"
                    ),
                )
            )

    # §5 — a new action_type not on any allowlist
    known = {a for actions in _all_allowlisted() for a in actions}
    for m in re.finditer(r"""action_type\s*[=:]\s*["']([a-z_]+)["']""", joined):
        if m.group(1) not in known:
            out.append(
                ReviewFinding(
                    severity="MAJOR",
                    file=target,
                    line=_first_added_line(diff),
                    message=f"action_type `{m.group(1)}` is not on any agent allowlist",
                    evidence="security.md §5 (every proposed action passes the allowlist)",
                )
            )

    # §7 — a model call on a PII-shaped field with no scrub in the same block
    if re.search(r"\.complete(_structured)?\(", joined) and _PII_VAR.search(joined):
        if "scrub" not in joined and "redact" not in joined:
            out.append(
                ReviewFinding(
                    severity="BLOCKER",
                    file=target,
                    line=_first_added_line(diff),
                    message=(
                        "model call includes a PII-shaped field with no "
                        "scrub/redact in the same block"
                    ),
                    evidence="security.md §7 — payloads scrubbed for PII before a model prompt",
                )
            )

    # agent-authored scenario — needs a human reviewer
    if re.search(r"authored_by:\s*agent", joined) and any("scenarios/" in f for f in files):
        out.append(
            ReviewFinding(
                severity="MAJOR",
                file=target,
                message=(
                    "agent-authored scenario (`authored_by: agent`) — a human "
                    "reviewer must sign off before merge"
                ),
                evidence=(
                    "agent-plan Phase 12 — an agent-authored scenario cannot "
                    "merge without a human reviewer"
                ),
            )
        )
    return out


# --- deterministic checks (interpreted, not authoritative on pass/fail) --------


def _deterministic(pr_id: str) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for hit in ci_store.security_scan(pr_id):
        sev = "BLOCKER" if hit.get("severity") == "HIGH" else "MAJOR"
        out.append(
            ReviewFinding(
                severity=sev,
                file=str(hit.get("file", "?")),
                line=int(hit.get("line", 0)),
                message=str(hit.get("message", "")),
                evidence=f"security scan {hit.get('rule')}",
            )
        )
    tests = ci_store.tests(pr_id)
    if tests.get("failed"):
        out.append(
            ReviewFinding(
                severity="BLOCKER",
                file="(tests)",
                message=f"{tests['failed']} test(s) failing: {', '.join(tests.get('failing', []))}",
                evidence="ci.run_tests",
            )
        )
    cov = ci_store.coverage(pr_id)
    if cov.get("delta_pct", 0.0) <= -1.0:
        out.append(
            ReviewFinding(
                severity="MINOR",
                file="(coverage)",
                message=(
                    f"coverage {cov['delta_pct']:+.1f}% "
                    f"({cov.get('uncovered_new_lines', 0)} new uncovered lines)"
                ),
                evidence="ci.get_test_coverage",
            )
        )
    for lint in ci_store.static_analysis(pr_id):
        out.append(
            ReviewFinding(
                severity="MINOR",
                file=str(lint.get("file", "?")),
                line=int(lint.get("line", 0)),
                message=f"{lint.get('tool')}: {lint.get('code')} {lint.get('message')}",
                evidence="ci.run_static_analysis",
            )
        )
    return out


def _eval_impact(pr_id: str, files: list[str]) -> list[ReviewFinding]:
    out: list[ReviewFinding] = []
    for f in files:
        m = re.search(r"scenarios/0*(\d+)_", f)
        if not m or "authored_by: agent" in (repo_store.get_diff(pr_id) or ""):
            continue
        sid = m.group(1)
        baseline = ci_store.eval_run(sid)
        out.append(
            ReviewFinding(
                severity="MAJOR" if ci_store.tests(pr_id).get("failed") else "MINOR",
                file=f,
                message=(
                    f"touched planted scenario {sid} — its eval must re-run "
                    f"(baseline: {baseline['passed']}/{baseline['runs']})"
                ),
                evidence="scenarios-first — docs/eval-scenarios.md is the spec",
            )
        )
    return out


# --- helpers -----------------------------------------------------------------


def _all_allowlisted() -> list[set[str]]:
    return list(_allowlists().values())


def _first_added_line(diff: str) -> int:
    m = re.search(r"@@ -\d+(?:,\d+)? \+(\d+)", diff)
    return int(m.group(1)) if m else 0


def _recommend(findings: list[ReviewFinding]) -> str:
    if any(f.severity in ("BLOCKER", "MAJOR") for f in findings):
        return "REQUEST_CHANGES"
    if findings:
        return "COMMENT"
    return "APPROVE"


def _summary(surfaces: list[str], findings: list[ReviewFinding], rec: str) -> str:
    cites = "; ".join(_SURFACE_STANDARD[s] for s in surfaces if s in _SURFACE_STANDARD)
    counts = ", ".join(
        f"{sev.lower()}×{sum(f.severity == sev for f in findings)}"
        for sev in ("BLOCKER", "MAJOR", "MINOR", "NIT")
        if any(f.severity == sev for f in findings)
    )
    head = f"surfaces: {', '.join(surfaces)}. {counts or 'no findings'}. → {rec}."
    return f"{head} standards: {cites}" if cites else head
