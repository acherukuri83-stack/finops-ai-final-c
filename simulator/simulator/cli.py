"""`make seed SCENARIO=<n|all>` entry point.

Always resets to a fresh, deterministic baseline first, then applies the
requested scenario(s)' plant blocks on top. Reseeding is therefore always a
clean, reproducible operation — never a diff against whatever was there before.
"""

from pathlib import Path

import typer

from simulator import baseline, events, planter
from simulator.db import connect
from simulator.scenario import Scenario

app = typer.Typer(no_args_is_help=True)
SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


@app.callback()
def main() -> None:
    """FinOps AI simulator."""


@app.command()
def seed(scenario: str = "all") -> None:
    files = sorted(SCENARIOS.glob("*.yaml"))
    if scenario != "all":
        files = [f for f in files if f.name.startswith(f"{int(scenario):03d}_")]
        if not files:
            raise typer.BadParameter(f"no scenario file for SCENARIO={scenario}")

    with connect() as conn:
        typer.echo("[seed] baseline: populating...")
        baseline.populate(conn)
        typer.echo("[seed] baseline: done")
        for f in files:
            sc = Scenario.load(f)
            if sc.unknown_plant_keys():
                raise typer.BadParameter(f"{f.name}: unknown plant keys {sc.unknown_plant_keys()}")
            if sc.leaks():
                raise typer.BadParameter(
                    f"{f.name}: interpretive language in planted data: {sc.leaks()}"
                )
            planter.plant(conn, sc)
            typer.echo(f"[seed] scenario {sc.id} {sc.name}: planted")


@app.command()
def emit(
    trade: str = typer.Option(..., help="trade id, e.g. T100245"),
    code: str = typer.Option("", help="failure_code (default: the trade's own)"),
    deadline: str = typer.Option("", help="ISO-8601; inside 60 min -> HIGH priority"),
) -> None:
    """Publish a FAILED settlement event for a seeded trade onto the platform outbox."""
    with connect() as conn:
        key = events.emit_settlement_failed(
            conn, trade, failure_code=code or None, deadline=deadline or None
        )
    typer.echo(f"[emit] FAILED {trade} -> outbox (dedup {key})")


if __name__ == "__main__":
    app()
