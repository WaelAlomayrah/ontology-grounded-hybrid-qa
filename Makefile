.DEFAULT_GOAL := help
.PHONY: help env build up up-gpu down restart logs ps ingest-sample ingest-kg2qa test test-integration lint format typecheck evaluate smoke-test clean reset-data
help: ; @echo "env build up up-gpu down restart logs ps ingest-sample ingest-kg2qa test test-integration lint format typecheck evaluate smoke-test clean reset-data"
env: ; test -f .env || cp .env.example .env
build: ; docker compose build
up: env ; docker compose up -d --build
up-gpu: env ; docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
down: ; docker compose down
restart: ; docker compose restart
logs: ; docker compose logs -f
ps: ; docker compose ps
ingest-sample: ; docker compose --profile tools run --rm data-loader --dataset sample --reset --load-graph --load-vectors
ingest-kg2qa: ; docker compose --profile tools run --rm data-loader --dataset kg2qa --reset --load-graph --load-vectors
ingest-policeuk: ; docker compose --profile tools run --rm data-loader --dataset policeuk --reset --download --load-graph --load-vectors --force "Thames Valley Police" --months 12
test: ; cd backend && pytest tests/unit tests/api
test-integration: ; cd backend && pytest -m integration tests/integration
lint: ; cd backend && ruff check .
format: ; cd backend && ruff format .
typecheck: ; cd backend && mypy app && cd ../frontend && npm run typecheck
evaluate: ; curl -X POST http://localhost:$${BACKEND_PORT:-8000}/api/v1/evaluation/run
smoke-test: ; ./scripts/smoke_test.sh
clean: ; docker compose down --remove-orphans
reset-data: ; docker compose down -v
