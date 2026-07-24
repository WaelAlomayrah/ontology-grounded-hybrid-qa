#!/usr/bin/env sh
set -eu
docker compose --profile tools run --rm data-loader --dataset "${1:-sample}" --reset --load-graph --load-vectors
