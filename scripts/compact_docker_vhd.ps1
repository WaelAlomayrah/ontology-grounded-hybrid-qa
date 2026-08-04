$ErrorActionPreference = "Stop"
$vhdPath = "C:\Users\Wael\AppData\Local\Docker\wsl\disk\docker_data.vhdx"
$resultPath = "D:\master-project\pilot-v1\data\runtime\docker-vhd-compaction.json"

if (Get-Process -Name "Docker Desktop", "com.docker.backend" -ErrorAction SilentlyContinue) {
    throw "Docker Desktop must be stopped before compaction"
}
if (-not (Test-Path -LiteralPath $vhdPath)) {
    throw "Docker data VHD was not found"
}

$before = (Get-Item -LiteralPath $vhdPath -Force).Length
Import-Module Hyper-V
Optimize-VHD -Path $vhdPath -Mode Full
$after = (Get-Item -LiteralPath $vhdPath -Force).Length

New-Item -ItemType Directory -Path (Split-Path -Parent $resultPath) -Force | Out-Null
@{
    path = $vhdPath
    before_bytes = $before
    after_bytes = $after
    reclaimed_bytes = $before - $after
    completed_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
