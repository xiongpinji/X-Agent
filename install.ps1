# X-Agent one-command installer (Windows PowerShell).
#
#   powershell -ExecutionPolicy Bypass -File install.ps1         # install
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Dev    # with dev deps
#
# Steps: check Python >= 3.11 -> create/reuse venv -> pip install -e .
# -> generate .env from .env.development -> run `xagent doctor` self-check.
#
# Idempotent: re-running only fills in missing pieces; an already-working
# venv (backend importable + xagent entry point present) skips pip install.
[CmdletBinding()]
param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$VenvDir = "venv"
$EnvFile = ".env"
$EnvTemplate = ".env.development"
$MinMajor = 3
$MinMinor = 11

function Log([string]$Msg)  { Write-Host "==> $Msg" }
function Ok([string]$Msg)   { Write-Host "  [OK] $Msg" -ForegroundColor Green }
function Warn([string]$Msg) { Write-Host "  [WARN] $Msg" -ForegroundColor Yellow }
function Die([string]$Msg)  { Write-Host "  [FAIL] $Msg" -ForegroundColor Red; exit 1 }

# Return a python invocation (array of command + args) that is >= 3.11, or $null.
function Find-SystemPython {
    $candidates = @(
        @("py", "-3.13"), @("py", "-3.12"), @("py", "-3.11"),
        @("python"), @("python3"), @("py")
    )
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $check = "import sys; raise SystemExit(0 if sys.version_info >= ($MinMajor, $MinMinor) else 1)"
        & $exe @($candidate[1..($candidate.Count - 1)]) -c $check 2>$null
        if ($LASTEXITCODE -eq 0) { return ,$candidate }
    }
    return $null
}

function Get-VenvPython {
    $win = Join-Path $VenvDir "Scripts\python.exe"
    $nix = Join-Path $VenvDir "bin/python"
    if (Test-Path $win) { return $win }
    if (Test-Path $nix) { return $nix }
    return $null
}

function Get-VenvXagent {
    $win = Join-Path $VenvDir "Scripts\xagent.exe"
    $nix = Join-Path $VenvDir "bin/xagent"
    if (Test-Path $win) { return $win }
    if (Test-Path $nix) { return $nix }
    return $null
}

function Test-BackendImportable([string]$VenvPython) {
    & $VenvPython -c "import backend.app.settings, backend.app.core.agent" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

# Skip the heavy pip install when the venv is already fully usable.
function Test-ShouldSkipInstall {
    $vpy = Get-VenvPython
    if (-not $vpy) { return $false }
    if (-not (Get-VenvXagent)) { return $false }
    return (Test-BackendImportable $vpy)
}

# Copy the env template only when the target does not exist (never overwrite).
function Ensure-EnvFile {
    if (Test-Path $EnvFile) {
        Ok "$EnvFile 已存在，保留现状"
        return
    }
    if (Test-Path $EnvTemplate) {
        Copy-Item $EnvTemplate $EnvFile
        Ok "已从 $EnvTemplate 生成 $EnvFile"
    } else {
        Warn "$EnvTemplate 不存在，跳过 .env 生成"
    }
}

if (-not ((Test-Path "pyproject.toml") -and (Test-Path "backend"))) {
    Die "请在 X-Agent 仓库根目录运行本脚本"
}

Log "X-Agent 一条命令安装 (Track D2)"

# ─── 1/5 Python >= 3.11 ──────────────────────────────────────────────────────
Log "[1/5] 检查 Python >= $MinMajor.$MinMinor"
$venvPy = Get-VenvPython
if ($venvPy) {
    $ver = & $venvPy --version 2>&1
    Ok "复用已有 venv: $ver"
} else {
    $sysPy = Find-SystemPython
    if (-not $sysPy) { Die "未找到 Python >= $MinMajor.$MinMinor，请先安装: https://www.python.org/downloads/" }
    $ver = & $sysPy[0] @($sysPy[1..($sysPy.Count - 1)]) --version 2>&1
    Ok "系统 Python: $ver"
    Log "[2/5] 创建虚拟环境 $VenvDir/"
    & $sysPy[0] @($sysPy[1..($sysPy.Count - 1)]) -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Die "venv 创建失败" }
    $venvPy = Get-VenvPython
    if (-not $venvPy) { Die "venv 创建后未找到 python" }
    Ok "venv 已创建"
}
if ($env:VIRTUAL_ENV) { Warn "检测到已激活的 VIRTUAL_ENV=$($env:VIRTUAL_ENV)，本脚本始终使用 ./$VenvDir" }

# ─── 2-3/5 install (skip heavy work when venv is already usable) ─────────────
if (Test-ShouldSkipInstall) {
    Log "[2/5] 依赖安装: 跳过（venv 可用且 backend 可导入，幂等复用）"
    Ok "xagent 入口: $(Get-VenvXagent)"
} else {
    $extras = ""
    if ($Dev) { $extras = "[dev]" }
    Log "[2/5] 安装依赖 pip install -e .$extras"
    & $venvPy -m pip install --upgrade pip | Out-Null
    & $venvPy -m pip install -e ".$extras"
    if ($LASTEXITCODE -ne 0) { Die "依赖安装失败" }
    Ok "依赖安装完成"
}
if ($Dev) {
    & $venvPy -c "import pytest" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Log "[3/5] 补齐 dev 依赖"
        & $venvPy -m pip install -e ".[dev]"
        if ($LASTEXITCODE -ne 0) { Die "dev 依赖安装失败" }
        Ok "dev 依赖已补齐"
    } else {
        Log "[3/5] dev 依赖已就绪，跳过"
    }
} else {
    Log "[3/5] 未指定 -Dev，跳过 dev 依赖"
}

# ─── 4/5 .env ────────────────────────────────────────────────────────────────
Log "[4/5] 配置 .env"
Ensure-EnvFile

# ─── 5/5 doctor ──────────────────────────────────────────────────────────────
Log "[5/5] 运行 xagent doctor 自检"
& $venvPy -m cli.main doctor
$doctorRc = $LASTEXITCODE
if ($doctorRc -ne 0) { Warn "doctor 存在失败项（见上方 FAIL），请先按修复建议处理" }

$xagentBin = Get-VenvXagent
if (-not $xagentBin) { $xagentBin = "$venvPy -m cli.main" }
Write-Host ""
Write-Host "==> 安装完成。下一步:"
Write-Host "  1. $xagentBin doctor                                    # 环境自检"
Write-Host "  2. $xagentBin agent run `"你好`" --mode local             # 本地模式跑一个任务"
Write-Host "  3. $venvPy -m uvicorn backend.app.main:app --port 8000  # 启动 API 服务"
Write-Host ""

exit $doctorRc
