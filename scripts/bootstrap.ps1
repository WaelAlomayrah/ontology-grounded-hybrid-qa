if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
docker compose --profile tools run --rm data-loader --dataset sample --reset --load-graph --load-vectors
& "$PSScriptRoot/smoke_test.ps1"
