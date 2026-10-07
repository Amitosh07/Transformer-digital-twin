param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("up", "seed", "reset", "down")][string]$Command,
    [switch]$Yes,
    [switch]$IncludeTransformers,
    [int]$Rows=2000
)
$ErrorActionPreference = "Stop"
$demoBackendRoot = Split-Path $PSScriptRoot -Parent
Push-Location $demoBackendRoot
try {
    if (-not (Test-Path -LiteralPath .env)) {
        Copy-Item -LiteralPath .env.example -Destination .env
    }
    switch ($Command) {
        up { docker compose -f docker-compose.backend.yml up --build -d --wait --wait-timeout 180 }
        seed { docker compose -f docker-compose.backend.yml exec -T backend python scripts/seed_demo.py --rows $Rows }
        reset {
            if (-not $Yes) { throw "Reset requires -Yes" }
            $demoResetArgs = @("compose", "-f", "docker-compose.backend.yml", "exec", "-T", "backend", "python", "scripts/reset_demo.py", "--yes")
            if ($IncludeTransformers) { $demoResetArgs += "--include-transformers" }
            & docker @demoResetArgs
        }
        down { docker compose -f docker-compose.backend.yml down }
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed ($LASTEXITCODE)" }
} finally { Pop-Location }
