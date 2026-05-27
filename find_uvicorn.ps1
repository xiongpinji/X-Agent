$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn backend.app.main:app*' }
$procs | Select-Object ProcessId,ParentProcessId,CommandLine | Format-List
