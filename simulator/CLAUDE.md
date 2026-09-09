# simulator — conventions
- `baseline.py`: seeded RNG population; deterministic ids. `planter.py`: one handler per `plant:` key; unknown key = error.
- `tables.py` mirrors the Java Flyway schema by hand; `finance_tables.py` mirrors the **platform-tier** prime-finance tables (owned by `ai-platform/mcp_servers/_finance_store.py`, `CREATE TABLE IF NOT EXISTS`, no Flyway). `finance_baseline.py` populates them each `make seed` (the `LN-5001` / `MC-9001` / `CA-7001` / `CB-8001` demo ids on `ACC-88213`). Keep both mirror files in sync with their ai-platform counterparts by hand.
- Scenario YAML = facts only under `plant:`. `expect:` is read by evals, never by the planter.
- The leak test (`scenario.leaks()`) fails the build if planted text contains interpretive language. Do not "help" the agent through data.
- Baseline must include failed trades with causes other than the planted scenario, and healthy trades for HEDGE_FUND_101.
- Every planted scenario carries 3–8 corroborating log lines with timestamps aligned to its own timeline (Sc. 10: none).
