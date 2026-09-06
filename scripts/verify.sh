#!/usr/bin/env bash
# Run before declaring any task done. Fails on the first problem.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== schema: migrate (for simulator's DB-backed tests)"
./scripts/migrate.sh

echo "== python: ruff"
(cd ai-platform && uv run ruff format --check . && uv run ruff check .)
(cd simulator && uv run ruff format --check . && uv run ruff check .)
echo "== python: mypy"
(cd ai-platform && uv run mypy .)
(cd simulator && uv run mypy .)
echo "== python: pytest (non-eval)"
(cd ai-platform && uv run pytest -m "not eval" -q)
(cd simulator && uv run pytest -q)
echo "== java: mvn test"
(cd enterprise && mvn -q test)
echo "== portal: lint + tsc"
(cd portal && npm run lint --silent && npx tsc --noEmit)
echo "== verify: OK"
