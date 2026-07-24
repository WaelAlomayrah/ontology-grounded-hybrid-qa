#!/usr/bin/env sh
set -eu
base="http://localhost:${BACKEND_PORT:-8000}"
curl -fsS "$base/health"
curl -fsS "$base/ready"
curl -fsS "$base/api/v1/graph/stats"
curl -fsS -H 'Content-Type: application/json' -d '{"question":"Which vendor supplies the system used by Project Atlas?","mode":"hybrid"}' "$base/api/v1/retrieve"
curl -fsS -H 'Content-Type: application/json' -d '{"question":"What is the CEO favorite restaurant?","mode":"hybrid"}' "$base/api/v1/chat"
