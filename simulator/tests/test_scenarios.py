from pathlib import Path

from simulator.scenario import Scenario

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


def test_all_scenarios_validate_and_have_no_leaks() -> None:
    files = sorted(SCENARIOS.glob("*.yaml"))
    assert files, "no scenario files"
    for f in files:
        sc = Scenario.load(f)
        assert not sc.unknown_plant_keys(), f"{f.name}: {sc.unknown_plant_keys()}"
        assert not sc.leaks(), f"{f.name}: leaks {sc.leaks()}"
        assert "root_cause" in sc.expect or "outcome" in sc.expect, f"{f.name}: expect missing"


def test_scenario_1_shape() -> None:
    sc = Scenario.load(SCENARIOS / "001_counterparty_ssi_stale.yaml")
    ssi = sc.plant["accounts.ssi"]
    assert [v["dtc"] for v in ssi] == ["5678", "1234"]
    assert sc.plant["affirmations"][0]["cpty_dtc"] == "5678"
    assert sc.expect["rejected_alternatives_must_include"] == ["update_ssi"]
