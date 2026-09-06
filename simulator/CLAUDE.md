# simulator — conventions
- `baseline.py`: seeded RNG population; deterministic ids. `planter.py`: one handler per `plant:` key; unknown key = error.
- Scenario YAML = facts only under `plant:`. `expect:` is read by evals, never by the planter.
- The leak test (`scenario.leaks()`) fails the build if planted text contains interpretive language. Do not "help" the agent through data.
- Baseline must include failed trades with causes other than the planted scenario, and healthy trades for HEDGE_FUND_101.
- Every planted scenario carries 3–8 corroborating log lines with timestamps aligned to its own timeline (Sc. 10: none).
