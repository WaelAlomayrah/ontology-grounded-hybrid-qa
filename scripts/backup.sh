#!/usr/bin/env sh
set -eu
docker compose stop fuseki milvus
docker run --rm -v ontology-ai-pilot_fuseki-data:/source:ro -v "$PWD:/backup" alpine:3.21 tar czf /backup/fuseki-backup.tgz -C /source .
docker compose start fuseki milvus
