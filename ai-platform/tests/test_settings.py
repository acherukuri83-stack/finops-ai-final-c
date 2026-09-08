"""Config normalisation — managed Postgres URLs must gain the psycopg driver."""

from __future__ import annotations

from platform_api.settings import Settings


def test_bare_postgresql_url_gets_the_psycopg_driver() -> None:
    s = Settings(database_url="postgresql://u:p@host:5432/finops")
    assert s.database_url == "postgresql+psycopg://u:p@host:5432/finops"


def test_an_already_qualified_url_is_left_alone() -> None:
    s = Settings(database_url="postgresql+psycopg://u:p@host/finops")
    assert s.database_url == "postgresql+psycopg://u:p@host/finops"
