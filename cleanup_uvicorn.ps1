$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn backend.app.main:app*' }

if (-not $procs) {
    Write-Host 'No backend uvicorn processes found.'
    exit 0
}

Write-Host 'Found backend uvicorn processes:'
$procs | Select-Object ProcessId, ParentProcessId, CommandLine | Format-List

foreach ($p in $procs) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped PID $($p.ProcessId)"
    }
    catch {
        Write-Host "Failed to stop PID $($p.ProcessId): $($_.Exception.Message)"
    }
}
