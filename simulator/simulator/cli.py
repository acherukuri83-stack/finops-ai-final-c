"""`make seed SCENARIO=<n|all>` entry point. Baseline + planter arrive in W1 PR2."""

from pathlib import Path

import typer

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
    for f in files:
        sc = Scenario.load(f)
        if sc.unknown_plant_keys():
            raise typer.BadParameter(f"{f.name}: unknown plant keys {sc.unknown_plant_keys()}")
        if sc.leaks():
            raise typer.BadParameter(
                f"{f.name}: interpretive language in planted data: {sc.leaks()}"
            )
        typer.echo(f"[seed] scenario {sc.id} {sc.name}: validated (planter not yet implemented)")


if __name__ == "__main__":
    app()
