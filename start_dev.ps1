# X-Agent 开发环境一键启动脚本
# 用法: .\start_dev.ps1
# 停止: Ctrl+C 或 .\stop_dev.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  X-Agent Dev Environment Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ─── 1. 加载环境变量 ───────────────────────────────────────────────
$envFile = Join-Path $root ".env.development"
if (Test-Path $envFile) {
    Write-Host "[1/4] Loading .env.development ..." -ForegroundColor Yellow
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $parts = $line -split "=", 2
            if ($parts.Count -eq 2) {
                [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
            }
        }
    }
    Write-Host "  OK: Environment loaded" -ForegroundColor Green
} else {
    Write-Host "  WARN: .env.development not found, using defaults" -ForegroundColor DarkYellow
}

# 确保关键变量
if (-not $env:XAGENT_DEEPSEEK_API_KEY) {
    Write-Host "  ERROR: XAGENT_DEEPSEEK_API_KEY not set!" -ForegroundColor Red
    exit 1
}

# ─── 2. 清理残留进程 ──────────────────────────────────────────────
Write-Host "[2/4] Cleaning stale processes ..." -ForegroundColor Yellow
$backendConn = Get-NetTCPConnection -LocalPort 8099 -State Listen -ErrorAction SilentlyContinue
if ($backendConn) {
    $backendConn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
    Write-Host "  Stopped old backend on 8099" -ForegroundColor DarkYellow
}
$frontendConn = Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue
if ($frontendConn) {
    $frontendConn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
    Write-Host "  Stopped old frontend on 3001" -ForegroundColor DarkYellow
}
Write-Host "  OK: Ports 8099, 3001 free" -ForegroundColor Green

# ─── 3. 启动后端 ──────────────────────────────────────────────────
Write-Host "[3/4] Starting backend (uvicorn :8099) ..." -ForegroundColor Yellow
$backendDir = Join-Path $root "backend"
$venvPython = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  ERROR: venv not found at $venvPython" -ForegroundColor Red
    Write-Host "  Run: python -m venv venv && venv\Scripts\pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}
$backendProc = Start-Process -FilePath $venvPython -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8099", "--reload" -WorkingDirectory $root -PassThru -NoNewWindow
Write-Host "  Backend PID: $($backendProc.Id)" -ForegroundColor Green

# 等待后端就绪
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:8099/health" -TimeoutSec 2 -ErrorAction Stop
        if ($h.status -eq "ok") { $ready = $true; break }
    } catch { }
}
if ($ready) {
    Write-Host "  OK: Backend ready at http://localhost:8099" -ForegroundColor Green
} else {
    Write-Host "  WARN: Backend not responding after 30s (check logs)" -ForegroundColor DarkYellow
}

# ─── 4. 启动前端 ──────────────────────────────────────────────────
Write-Host "[4/4] Starting frontend (vite :3001) ..." -ForegroundColor Yellow
$frontendDir = Join-Path $root "frontend"
$nodePath = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $nodePath) {
    Write-Host "  ERROR: node not found in PATH" -ForegroundColor Red
    exit 1
}
$frontendProc = Start-Process -FilePath $nodePath -ArgumentList "node_modules/vite/bin/vite.js", "--port", "3001", "--host" -WorkingDirectory $frontendDir -PassThru -NoNewWindow
Write-Host "  Frontend PID: $($frontendProc.Id)" -ForegroundColor Green

Start-Sleep -Seconds 3
$feReady = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:3001/" -TimeoutSec 5 -ErrorAction Stop
    $feReady = ($r.StatusCode -eq 200)
} catch { }
if ($feReady) {
    Write-Host "  OK: Frontend ready at http://localhost:3001" -ForegroundColor Green
} else {
    Write-Host "  WARN: Frontend may still be starting..." -ForegroundColor DarkYellow
}

# ─── Summary ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  X-Agent Dev Environment Ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8099  (PID $($backendProc.Id))"
Write-Host "  Frontend: http://localhost:3001  (PID $($frontendProc.Id))"
Write-Host "  API Docs: http://localhost:8099/docs"
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host ""

# 等待用户中断
try {
    while ($true) {
        Start-Sleep -Seconds 5
        if ($backendProc.HasExited) {
            Write-Host "Backend exited (code=$($backendProc.ExitCode))" -ForegroundColor Red
            break
        }
        if ($frontendProc.HasExited) {
            Write-Host "Frontend exited (code=$($frontendProc.ExitCode))" -ForegroundColor Red
            break
        }
    }
} finally {
    Write-Host "Shutting down..." -ForegroundColor Yellow
    if (-not $backendProc.HasExited) { Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue }
    if (-not $frontendProc.HasExited) { Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "Done." -ForegroundColor Green
}
