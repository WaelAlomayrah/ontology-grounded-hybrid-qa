$port = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { '8000' }
Invoke-RestMethod -Method Post "http://localhost:$port/api/v1/evaluation/run"
