param(
    [ValidateRange(1, 1024)][double]$MinimumFreeGiB = 2.75,
    [ValidateRange(5, 300)][int]$IntervalSeconds = 30,
    [Parameter(Mandatory = $true)][string]$LogPath,
    [switch]$Once
)
$ErrorActionPreference = 'Stop'
$fleetRepo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$fleetCompose = Join-Path $fleetRepo 'docker-compose.operational-existing.yml'
do {
    $fleetDisks = @(Get-PSDrive C, D | Select-Object Name, Free)
    $fleetC = ($fleetDisks | Where-Object Name -eq 'C').Free
    $fleetState = [ordered]@{ time = [DateTime]::UtcNow.ToString('o'); disks = $fleetDisks; minimumFreeGiB = $MinimumFreeGiB; sourcePaused = $false }
    if ($fleetC -lt $MinimumFreeGiB * 1GB) {
        # Retain every container, volume, SQL row and pending delivery entry.
        # Bridge stays running to confirm real SQL receipts; no auto restart.
        & docker compose -f $fleetCompose --profile primary stop --timeout 30 modbus-simulator
        if ($LASTEXITCODE -ne 0) { throw 'Disk guard could not pause the operational source' }
        $fleetState.sourcePaused = $true
    }
    $fleetState | ConvertTo-Json -Depth 4 -Compress | Add-Content -LiteralPath $LogPath -Encoding utf8
    if ($fleetState.sourcePaused -or $Once) { break }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
