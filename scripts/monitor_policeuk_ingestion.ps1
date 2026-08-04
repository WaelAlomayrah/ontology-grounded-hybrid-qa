param(
    [string]$ContainerName = "policeuk-vector-streaming",
    [int]$IntervalSeconds = 10
)

$ErrorActionPreference = "SilentlyContinue"
$projectRoot = Split-Path -Parent $PSScriptRoot
$checkpointPath = Join-Path $projectRoot "data\policeuk\processed\vector-checkpoint.json"
$barWidth = 40

while ($true) {
    $containerJson = docker inspect $ContainerName 2>$null
    $container = if ($containerJson) { @($containerJson | ConvertFrom-Json)[0] } else { $null }
    $milvusJson = docker inspect ontology-ai-pilot-milvus-1 2>$null
    $milvus = if ($milvusJson) { @($milvusJson | ConvertFrom-Json)[0] } else { $null }
    $checkpoint = if (Test-Path -LiteralPath $checkpointPath) {
        Get-Content -LiteralPath $checkpointPath -Raw | ConvertFrom-Json
    } else {
        $null
    }

    Clear-Host
    Write-Host "Police.uk ingestion status" -ForegroundColor Cyan
    Write-Host (Get-Date -Format "yyyy-MM-dd HH:mm:ss") -ForegroundColor DarkGray
    Write-Host ""

    if (-not $checkpoint) {
        Write-Host "Checkpoint not found: $checkpointPath" -ForegroundColor Red
    } else {
        $processed = [long]$checkpoint.processed_documents
        $total = [long]$checkpoint.total_documents
        $remaining = [Math]::Max(0, $total - $processed)
        $percent = if ($total -gt 0) { 100.0 * $processed / $total } else { 0.0 }
        $filled = [Math]::Min($barWidth, [Math]::Max(0, [int][Math]::Floor($barWidth * $percent / 100)))
        $bar = ("#" * $filled) + ("-" * ($barWidth - $filled))

        Write-Host ("  [{0}] {1:N1}%" -f $bar, $percent) -ForegroundColor Green
        Write-Host ""
        Write-Host ("  - Progress: {0:N0} / {1:N0}  {2:N1}%" -f $processed, $total, $percent)
        Write-Host ("  - Remaining: approximately {0:N0}" -f $remaining)
        Write-Host ("  - New vectors generated: {0:N0}" -f [long]$checkpoint.vectors_generated)
        Write-Host ("  - Existing vectors reused: {0:N0}" -f [long]$checkpoint.vectors_reused)
    }

    $containerState = if ($container) { [string]$container.State.Status } else { "not found" }
    $containerId = if ($container) { ([string]$container.Id).Substring(0, 12) } else { "n/a" }
    $oomKilled = if ($container -and $container.State.OOMKilled) { "yes" } else { "no" }
    $milvusState = if (-not $milvus) {
        "not found"
    } elseif ($milvus.State.Status -eq "running" -and $milvus.State.Health.Status -eq "healthy") {
        "running and healthy"
    } elseif ($milvus.State.Health.Status) {
        "$($milvus.State.Status) and $($milvus.State.Health.Status)"
    } else {
        [string]$milvus.State.Status
    }

    Write-Host ("  - Container: {0}" -f $ContainerName)
    Write-Host ("  - Container ID: {0}" -f $containerId)
    Write-Host ("  - Container state: {0}" -f $containerState)
    Write-Host ("  - Milvus: {0}" -f $milvusState)
    Write-Host ("  - OOM killed: {0}" -f $oomKilled)
    Write-Host ("  - Checkpoint: {0}" -f $(if ($checkpoint) { "working" } else { "unavailable" }))
    Write-Host "  - Fuseki graph: unchanged"
    Write-Host ""

    if ($containerState -ne "running") {
        Write-Host "Ingestion is no longer running. Press any key to close." -ForegroundColor Yellow
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        break
    }

    Write-Host "Refreshing every $IntervalSeconds seconds. Press Ctrl+C to stop." -ForegroundColor DarkGray
    Start-Sleep -Seconds $IntervalSeconds
}
