#!/usr/bin/env sh
set -eu
curl -fsS -X POST "http://localhost:${BACKEND_PORT:-8000}/api/v1/evaluation/run"
