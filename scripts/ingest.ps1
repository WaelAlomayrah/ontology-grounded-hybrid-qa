param([ValidateSet('sample','kg2qa')][string]$Dataset='sample')
docker compose --profile tools run --rm data-loader --dataset $Dataset --reset --load-graph --load-vectors
