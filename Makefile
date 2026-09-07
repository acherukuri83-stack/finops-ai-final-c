.PHONY: up down migrate seed ingest run portal test eval verify

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	./scripts/migrate.sh

seed: migrate
	cd simulator && uv run python -m simulator.cli seed --scenario $(or $(SCENARIO),all)

ingest:
	cd ai-platform && uv run python -m knowledge.ingest $(if $(FIXTURES),--fixtures $(FIXTURES),)

run:
	cd ai-platform && uv run uvicorn platform_api.main:app --host 0.0.0.0 --port 8000 --reload

portal:
	cd portal && npm run dev

test: migrate
	cd ai-platform && uv run pytest -m "not eval and not contract" -q
	cd simulator && uv run pytest -q
	cd enterprise && mvn -q test
	cd portal && npm run lint && npx tsc --noEmit

eval:
	cd ai-platform && uv run pytest -m eval -q evals $(if $(SCENARIO),-k "scenario_$(SCENARIO)",)

verify:
	./scripts/verify.sh
