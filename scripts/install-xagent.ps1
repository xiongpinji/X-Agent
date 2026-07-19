param(
  [switch]$Execute,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DoExecute = [bool]$Execute

$Commands = @(
  @{
    Display = 'python -m venv venv'
    Script = { & python -m venv venv }
  },
  @{
    Display = '.\venv\Scripts\python -m pip install --upgrade pip'
    Script = { & .\venv\Scripts\python -m pip install --upgrade pip }
  },
  @{
    Display = '.\venv\Scripts\python -m pip install -e ".[dev,cli]"'
    Script = { & .\venv\Scripts\python -m pip install -e ".[dev,cli]" }
  },
  @{
    Display = 'Push-Location frontend; npm ci; npm run type-check; Pop-Location'
    Script = {
      Push-Location frontend
      try {
        & npm ci
        if ($LASTEXITCODE -ne 0) {
          throw "Command failed with exit code ${LASTEXITCODE}: npm ci"
        }
        & npm run type-check
      } finally {
        Pop-Location
      }
      if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: npm run type-check"
      }
    }
  },
  @{
    Display = '.\venv\Scripts\python scripts/xagent_doctor.py --json'
    Script = { & .\venv\Scripts\python scripts/xagent_doctor.py --json }
  }
)

$Mode = "dry-run"
if ($DoExecute) {
  $Mode = "execute"
}
Write-Host "X-Agent installer ($Mode)"
Write-Host "Root: $Root"

foreach ($Command in $Commands) {
  Write-Host "> $($Command.Display)"
  if ($DoExecute) {
    Push-Location $Root
    try {
      Invoke-Command -ScriptBlock $Command.Script
      if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $($Command.Display)"
      }
    } finally {
      Pop-Location
    }
  }
}

if (-not $DoExecute) {
  Write-Host "Dry-run only. Rerun with -Execute to apply. This script does not modify global PATH."
}
