param(
  [switch]$Execute,
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DoExecute = [bool]$Execute

$Commands = @(
  'python -m venv venv',
  '.\venv\Scripts\python -m pip install --upgrade pip',
  '.\venv\Scripts\python -m pip install -e ".[dev,cli]"',
  'Push-Location frontend; npm ci; npm run type-check; Pop-Location',
  'python scripts/xagent_doctor.py --json'
)

$Mode = "dry-run"
if ($DoExecute) {
  $Mode = "execute"
}
Write-Host "X-Agent installer ($Mode)"
Write-Host "Root: $Root"

foreach ($Command in $Commands) {
  Write-Host "> $Command"
  if ($DoExecute) {
    Push-Location $Root
    try {
      Invoke-Expression $Command
    } finally {
      Pop-Location
    }
  }
}

if (-not $DoExecute) {
  Write-Host "Dry-run only. Rerun with -Execute to apply. This script does not modify global PATH."
}
