.PHONY: up down migrate seed emit ingest run portal test eval verify

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	./scripts/migrate.sh

seed: migrate
	cd simulator && uv run python -m simulator.cli seed --scenario $(or $(SCENARIO),all)

emit:  # publish an event: make emit TRADE=T100245 [DEADLINE=…]  |  make emit WIRE=W300917 [DEADLINE=…]
	cd simulator && uv run python -m simulator.cli emit $(if $(TRADE),--trade $(TRADE),) $(if $(WIRE),--wire $(WIRE),) $(if $(CODE),--code $(CODE),) $(if $(DEADLINE),--deadline $(DEADLINE),)

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
	cd ai-platform && uv run python -m evals.cli $(if $(SCENARIO),--scenario $(SCENARIO),) $(if $(N),--n $(N),)

verify:
	./scripts/verify.sh
