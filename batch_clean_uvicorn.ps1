$ErrorActionPreference = 'Stop'
$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn backend.app.main:app*' }
Write-Output 'Found backend uvicorn processes:'
$procs | Select-Object ProcessId,ParentProcessId,CommandLine | Format-List
foreach ($p in $procs) {
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Output ("Stopped PID $($p.ProcessId)")
}
