param(
  [string]$Python = "python",
  [string]$PilotChannel = "feishu",
  [string]$FinalGateOutput = ".xagent_runtime\reports\commercial-pilot-final-gate.json",
  [string]$OpsOutput = ".xagent_runtime\reports\commercial-pilot-ops-status.json",
  [string]$ManifestOutput = ".xagent_runtime\reports\commercial-pilot-delivery-manifest.json",
  [string]$ReceiptOutput = ".xagent_runtime\reports\commercial-pilot-delivery-receipt.json",
  [string]$ReceiptMarkdownOutput = ".xagent_runtime\reports\commercial-pilot-delivery-receipt.md"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Invoke-HandoffCommand {
  param(
    [string]$Display,
    [scriptblock]$Command
  )

  Write-Host "> $Display"
  Push-Location $Root
  try {
    Invoke-Command -ScriptBlock $Command
    if ($LASTEXITCODE -ne 0) {
      throw "Command failed with exit code ${LASTEXITCODE}: $Display"
    }
  } finally {
    Pop-Location
  }
}

Write-Host "X-Agent Feishu Pilot V1 final handoff"
Write-Host "Root: $Root"
Write-Host "Pilot channel: $PilotChannel"

Invoke-HandoffCommand `
  -Display "$Python scripts\commercial_pilot_final_gate.py --pilot-channel $PilotChannel" `
  -Command {
    & $Python scripts\commercial_pilot_final_gate.py `
      --pilot-channel $PilotChannel `
      --output $FinalGateOutput `
      --ops-output $OpsOutput `
      --manifest-output $ManifestOutput
  }

Invoke-HandoffCommand `
  -Display "$Python scripts\commercial_pilot_delivery_receipt.py" `
  -Command {
    & $Python scripts\commercial_pilot_delivery_receipt.py `
      --final-gate-report $FinalGateOutput `
      --ops-status-report $OpsOutput `
      --delivery-manifest-report $ManifestOutput `
      --output $ReceiptOutput `
      --markdown-output $ReceiptMarkdownOutput
  }

Write-Host "Feishu Pilot V1 final handoff completed."
Write-Host "Final gate report: $FinalGateOutput"
Write-Host "Operator status report: $OpsOutput"
Write-Host "Delivery manifest: $ManifestOutput"
Write-Host "Delivery receipt: $ReceiptOutput"
Write-Host "Delivery receipt markdown: $ReceiptMarkdownOutput"
