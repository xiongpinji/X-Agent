# Full Test Baseline — run all tests and produce a summary
# Usage: powershell -File scripts/full_test_baseline.ps1

$env:XAGENT_QDRANT_URL = ""
$env:XAGENT_MODE = "lite"
$env:XAGENT_LLM_BACKEND = "mock"
$env:XAGENT_REQUIRE_API_KEY = "false"

Write-Host "=" * 60
Write-Host "X-Agent Full Test Baseline"
Write-Host "=" * 60

# Run pytest with summary output
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportFile = "test_baseline_$timestamp.txt"

python -m pytest tests/ -q --timeout=120 -o addopts="" -p no:cov -p no:xdist `
    --ignore=tests/e2e --ignore=tests/performance `
    -k "not playwright and not notification_notification" `
    2>&1 | Tee-Object -FilePath $reportFile

Write-Host "`n"
Write-Host "=" * 60
Write-Host "Baseline saved to: $reportFile"
Write-Host "=" * 60

# Extract summary
$lastLine = Get-Content $reportFile | Select-Object -Last 3
Write-Host $lastLine
