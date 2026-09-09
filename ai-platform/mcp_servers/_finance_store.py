"""Shared backing for the seeded platform-tier domain stores — stockloan, margin,
corpactions, cash (prime finance), and wire (the optional Wires module). The name is
historical; `FinanceStore` is a generic seeded store, nothing in it is finance-specific.

Two modes behind one object, the same split `platform_api.cases` uses:

* **MEM** — in-process dicts for the unit suite, loaded from each domain's `seed()`
  snapshot. Byte-for-byte the fixtures the stores held before they were seeded, so
  `tests/test_{stockloan,margin,corpactions,cash}.py` are unaffected.
* **SQL** — Postgres tables the `simulator` seeds (`make seed`). Idempotent
  `CREATE TABLE IF NOT EXISTS` via SQLAlchemy Core — the `platform_api.store` /
  `knowledge.store` precedent, no Flyway, the Java tier stays out. Rows come back
  JSON-safe (dates → ISO strings, `Numeric` → float) so a SQL row and a MEM row are
  indistinguishable to the specialist and its prompts.

Mode is read once from `CASES_INMEMORY` (the whole ai-platform unit suite runs under it);
`set_memory(...)` overrides for a test — `tests/conftest.py` does this in its autouse
fixture.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import MetaData, Table, delete, insert, select

metadata = MetaData()

_USE_MEMORY = os.environ.get("CASES_INMEMORY") == "1"


def set_memory(on: bool) -> None:
    """Force MEM (True) or SQL (False) for every finance store. Test seam."""
    global _USE_MEMORY
    _USE_MEMORY = on


def use_memory() -> bool:
    return _USE_MEMORY


def _engine() -> Any:
    from platform_api.store import engine

    return engine()


def _jsonable(row: Mapping[str, Any]) -> dict[str, Any]:
    """A SQL row → the same primitive shape the MEM fixtures use."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat(sep="T", timespec="minutes")
        elif isinstance(value, date):
            out[key] = value.isoformat()
        elif isinstance(value, Decimal):
            out[key] = float(value)
        else:
            out[key] = value
    return out


class FinanceStore:
    """One seeded domain's data access. `read_tables` are seeded by the simulator;
    `action_table` is written at runtime when a human approves a proposal."""

    def __init__(
        self,
        *,
        name: str,
        read_tables: list[Table],
        action_table: Table,
        action_prefix: str,
        subject_key: str,
        seed: Callable[[], Mapping[str, list[dict[str, Any]]]],
    ) -> None:
        self.name = name
        self._read_tables = read_tables
        self._by_name = {t.name: t for t in [*read_tables, action_table]}
        self._action_table = action_table
        self._action_prefix = action_prefix
        self._subject_key = subject_key
        self._seed = seed
        self._mem: dict[str, list[dict[str, Any]]] = {}
        self._mem_actions: list[dict[str, Any]] = []
        self._mem_seq = 0
        self._mem_loaded = False

    # --- lifecycle ---------------------------------------------------------

    def _load_mem(self) -> None:
        self._mem = {name: [deepcopy(r) for r in rows] for name, rows in self._seed().items()}
        self._mem_loaded = True

    def reset(self) -> None:
        """MEM: reload the seed snapshot, drop recorded actions. SQL: drop recorded
        actions only (the simulator owns the seeded rows)."""
        if _USE_MEMORY:
            self._load_mem()
            self._mem_actions.clear()
            self._mem_seq = 0
        else:
            with _engine().begin() as conn:
                conn.execute(delete(self._action_table))

    def ensure_schema(self) -> None:
        metadata.create_all(
            _engine(), tables=[*self._read_tables, self._action_table], checkfirst=True
        )

    # --- reads -----------------------------------------------------------

    def get(self, table: str, **keys: Any) -> dict[str, Any] | None:
        rows = self.find(table, **keys)
        return rows[0] if rows else None

    def find(self, table: str, **filters: Any) -> list[dict[str, Any]]:
        active = {k: v for k, v in filters.items() if v is not None}
        if _USE_MEMORY:
            if not self._mem_loaded:
                self._load_mem()
            return [
                deepcopy(r)
                for r in self._mem.get(table, [])
                if all(r.get(k) == v for k, v in active.items())
            ]
        t = self._by_name[table]
        stmt = select(t)
        for k, v in active.items():
            stmt = stmt.where(t.c[k] == v)
        with _engine().connect() as conn:
            return [_jsonable(row) for row in conn.execute(stmt).mappings()]

    def update(self, table: str, keys: dict[str, Any], values: dict[str, Any]) -> int:
        """Update the rows in `table` matching `keys`. Returns the count changed. Used by
        human-initiated mutations (e.g. a WIRE_REVIEWER releasing a wire), not by agents."""
        if _USE_MEMORY:
            if not self._mem_loaded:
                self._load_mem()
            if table == self._action_table.name:
                # MEM action rows key the subject as `self._subject_key`, not `subject_id`.
                mem_keys = {
                    (self._subject_key if k == "subject_id" else k): v for k, v in keys.items()
                }
                rows = [
                    r for r in self._mem_actions if all(r.get(k) == v for k, v in mem_keys.items())
                ]
            else:
                rows = [
                    r
                    for r in self._mem.get(table, [])
                    if all(r.get(k) == v for k, v in keys.items())
                ]
            for r in rows:
                r.update(deepcopy(values))
            return len(rows)
        t = self._by_name[table]
        stmt = t.update()
        for k, v in keys.items():
            stmt = stmt.where(t.c[k] == v)
        with _engine().begin() as conn:
            return int(conn.execute(stmt.values(**values)).rowcount)

    # --- action write --------------------------------------------------

    def record_action(
        self, kind: str, subject_id: str, detail: dict[str, Any], approval_id: str
    ) -> dict[str, Any]:
        if _USE_MEMORY:
            self._mem_seq += 1
            row = {
                "action_id": f"{self._action_prefix}-{self._mem_seq:04d}",
                "kind": kind,
                self._subject_key: subject_id,
                "detail": deepcopy(detail),
                "status": "OPEN",
                "approval_id": approval_id,
            }
            self._mem_actions.append(row)
            return deepcopy(row)
        with _engine().begin() as conn:
            n = conn.execute(
                insert(self._action_table)
                .values(
                    kind=kind,
                    subject_id=subject_id,
                    detail=detail,
                    status="OPEN",
                    approval_id=approval_id,
                )
                .returning(self._action_table.c.id)
            ).scalar_one()
        return {
            "action_id": f"{self._action_prefix}-{int(n):04d}",
            "kind": kind,
            self._subject_key: subject_id,
            "detail": detail,
            "status": "OPEN",
            "approval_id": approval_id,
        }

    def actions(self) -> list[dict[str, Any]]:
        if _USE_MEMORY:
            return [deepcopy(a) for a in self._mem_actions]
        with _engine().connect() as conn:
            rows = conn.execute(
                select(self._action_table).order_by(self._action_table.c.id)
            ).mappings()
            return [
                {
                    "action_id": f"{self._action_prefix}-{r['id']:04d}",
                    "kind": r["kind"],
                    self._subject_key: r["subject_id"],
                    "detail": r["detail"],
                    "status": r["status"],
                    "approval_id": r["approval_id"],
                }
                for r in rows
            ]


def ensure_all_schemas() -> None:
    """Create every finance table. Called from `platform_api.store.ensure_schema()`.

    Imports the four domain stores first so their `Table`s are registered on `metadata`.
    """
    from mcp_servers.cash import store as _cash  # noqa: F401
    from mcp_servers.corpactions import store as _ca  # noqa: F401
    from mcp_servers.margin import store as _margin  # noqa: F401
    from mcp_servers.stockloan import store as _sl  # noqa: F401
    from mcp_servers.wire import store as _wire  # noqa: F401

    metadata.create_all(_engine(), checkfirst=True)
