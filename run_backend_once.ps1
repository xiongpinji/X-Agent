$ErrorActionPreference = 'Stop'
$proc = Start-Process -FilePath python -ArgumentList @('-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8003') -PassThru
Write-Output ("PID=$($proc.Id)")
Write-Output 'Started backend once.'
