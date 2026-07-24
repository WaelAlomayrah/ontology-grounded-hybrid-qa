#!/usr/bin/env sh
set -eu
[ -f .env ] || cp .env.example .env
docker compose up -d --build
docker compose --profile tools run --rm data-loader --dataset sample --reset --load-graph --load-vectors
./scripts/smoke_test.sh
