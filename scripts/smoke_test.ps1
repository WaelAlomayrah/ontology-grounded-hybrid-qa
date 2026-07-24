$port = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { '8000' }
$base = "http://localhost:$port"
Invoke-RestMethod "$base/health"
Invoke-RestMethod "$base/ready"
Invoke-RestMethod "$base/api/v1/graph/stats"
Invoke-RestMethod -Method Post -ContentType application/json -Body '{"question":"Which vendor supplies the system used by Project Atlas?","mode":"hybrid"}' "$base/api/v1/retrieve"
