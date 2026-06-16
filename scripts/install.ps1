[CmdletBinding()]
param(
    [ValidateSet("lite", "full")]
    [string]$Mode = $env:INSTALL_MODE,
    [switch]$Check
)

$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:XAGENT_REPO_URL) { $env:XAGENT_REPO_URL } else { "https://github.com/xiongpinji/X-Agent.git" }
$Branch = if ($env:XAGENT_INSTALL_BRANCH) { $env:XAGENT_INSTALL_BRANCH } else { "develop" }
$ZipUrl = if ($env:XAGENT_ZIP_URL) { $env:XAGENT_ZIP_URL } else { "https://github.com/xiongpinji/X-Agent/archive/refs/heads/$Branch.zip" }
$XAgentHome = if ($env:XAGENT_HOME) { $env:XAGENT_HOME } else { Join-Path $HOME ".xagent" }
$SourceDir = if ($env:XAGENT_SOURCE_DIR) { $env:XAGENT_SOURCE_DIR } else { Join-Path $XAgentHome "source" }
$EnvFile = if ($env:XAGENT_ENV_FILE) { $env:XAGENT_ENV_FILE } else { Join-Path $XAgentHome ".env" }
$HostName = if ($env:XAGENT_HOST) { $env:XAGENT_HOST } else { "127.0.0.1" }
$Port = if ($env:XAGENT_PORT) { $env:XAGENT_PORT } else { "8000" }

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message"
}

function Fail {
    param([string]$Message)
    throw "ERROR: $Message"
}

function Find-Python {
    $candidates = @()
    if ($env:PYTHON) { $candidates += $env:PYTHON }
    $candidates += @("py", "python3.12", "python3.11", "python3", "python")

    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $args = @()
        if ($candidate -eq "py") { $args += "-3.11" }
        $args += @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        try {
            & $candidate @args *> $null
            $candidateExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        if ($candidateExitCode -eq 0) {
            return @{ Command = $candidate; Prefix = $(if ($candidate -eq "py") { @("-3.11") } else { @() }) }
        }
    }
    Fail "Python 3.11+ is required. Install Python and rerun this script."
}

function Invoke-Python {
    param(
        [hashtable]$Python,
        [string[]]$Arguments
    )
    & $Python.Command @($Python.Prefix + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        Fail "Python command failed: $($Arguments -join ' ')"
    }
}

function Test-DockerCompose {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        & docker compose version *> $null
        if ($LASTEXITCODE -eq 0) { return "docker compose" }
    }
    $compose = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($compose) { return "docker-compose" }
    return $null
}

function Get-LocalSource {
    if ($PSScriptRoot) {
        $candidate = Resolve-Path (Join-Path $PSScriptRoot "..") -ErrorAction SilentlyContinue
        if ($candidate -and (Test-Path (Join-Path $candidate "pyproject.toml")) -and (Test-Path (Join-Path $candidate "backend"))) {
            return $candidate.Path
        }
    }
    return $null
}

function Ensure-Source {
    $local = Get-LocalSource
    if ($local) {
        $script:SourceDir = $local
        Write-Step "Using local source: $script:SourceDir"
        return
    }

    if (Test-Path (Join-Path $SourceDir ".git")) {
        Write-Step "Updating source at $SourceDir"
        git -C $SourceDir fetch --depth 1 origin $Branch
        git -C $SourceDir checkout $Branch
        git -C $SourceDir reset --hard "origin/$Branch"
        return
    }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Fail "git is required for full mode or local source checkout"
    }
    Write-Step "Cloning X-Agent into $SourceDir"
    New-Item -ItemType Directory -Force -Path (Split-Path $SourceDir) | Out-Null
    git clone --depth 1 --branch $Branch $RepoUrl $SourceDir
}

function Add-EnvIfMissing {
    param([string]$Key, [string]$Value)
    $text = if (Test-Path $EnvFile) { Get-Content $EnvFile -Raw } else { "" }
    if ($text -notmatch "(?m)^\s*(export\s+)?$([regex]::Escape($Key))=") {
        Add-Content -Path $EnvFile -Value "$Key=$Value"
    }
}

function Write-BaseEnv {
    New-Item -ItemType Directory -Force -Path $XAgentHome | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $XAgentHome "data") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $XAgentHome "logs") | Out-Null
    if (-not (Test-Path $EnvFile)) { New-Item -ItemType File -Path $EnvFile | Out-Null }

    Add-EnvIfMissing "XAGENT_APP_MODE" "development"
    Add-EnvIfMissing "XAGENT_REQUIRE_API_KEY" "false"
    Add-EnvIfMissing "XAGENT_LLM_BACKEND" "mock"
    Add-EnvIfMissing "XAGENT_MEMORY_BACKEND" "memory"
    Add-EnvIfMissing "XAGENT_TRACE_BACKEND" "jsonl"
    Add-EnvIfMissing "XAGENT_DATABASE_URL" "sqlite:///./data/xagent.db"
    Add-EnvIfMissing "XAGENT_RUN_STORE_PATH" "./data/runs.jsonl"
    Add-EnvIfMissing "XAGENT_TRACE_STORE_PATH" "./data/traces.jsonl"
    Add-EnvIfMissing "XAGENT_AUDIT_STORE_PATH" "./data/audit.jsonl"
    Add-EnvIfMissing "XAGENT_QDRANT_URL" ""
}

function Import-EnvFile {
    if (-not (Test-Path $EnvFile)) { return }

    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        if ($line.StartsWith("export ")) {
            $line = $line.Substring(7).Trim()
        }
        $separator = $line.IndexOf("=")
        if ($separator -le 0) { return }

        $key = $line.Substring(0, $separator).Trim()
        $value = $line.Substring($separator + 1).Trim()
        if (($value.Length -ge 2) -and (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        )) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

function Get-GenerateSecrets {
    $target = Join-Path $XAgentHome "generate_secrets.py"
    $local = Join-Path $SourceDir "scripts\generate_secrets.py"
    if (Test-Path $local) {
        Copy-Item $local $target -Force
        return $target
    }
    $uri = "https://raw.githubusercontent.com/xiongpinji/X-Agent/$Branch/scripts/generate_secrets.py"
    Invoke-WebRequest -Uri $uri -OutFile $target
    return $target
}

function Merge-Secrets {
    param([hashtable]$Python)
    $generator = Get-GenerateSecrets
    Invoke-Python $Python @($generator, "--env-file", $EnvFile, "--create")
}

function New-Venv {
    param([hashtable]$Python)
    $venv = Join-Path $XAgentHome "venv"
    $venvPython = Join-Path $venv "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Step "Creating virtual environment at $venv"
        Invoke-Python $Python @("-m", "venv", $venv)
    }
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed" }
    return $venvPython
}

function Install-Lite {
    param([hashtable]$Python)
    $venvPython = New-Venv $Python
    $local = Get-LocalSource
    if ($local) {
        $script:SourceDir = $local
        Write-Step "Installing X-Agent from local source"
        & $venvPython -m pip install -e "$SourceDir[cli]"
    } else {
        Write-Step "Installing X-Agent from $ZipUrl"
        & $venvPython -m pip install "x-agent-core[cli] @ $ZipUrl"
    }
    if ($LASTEXITCODE -ne 0) { Fail "X-Agent package install failed" }

    $binDir = Join-Path $XAgentHome "bin"
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    $cmdPath = Join-Path $binDir "xagent.cmd"
    $venvXagent = Join-Path $XAgentHome "venv\Scripts\xagent.exe"
    "@echo off`r`n`"$venvXagent`" %*`r`n" | Set-Content -Path $cmdPath -Encoding ASCII
    & $venvXagent --version
}

function Start-Lite {
    if ($env:XAGENT_START -eq "0") { return }
    $venvPython = Join-Path $XAgentHome "venv\Scripts\python.exe"
    $logPath = Join-Path $XAgentHome "logs\xagent.log"
    Write-Step "Starting X-Agent lite server on http://$HostName`:$Port"
    Import-EnvFile
    $errorLogPath = Join-Path $XAgentHome "logs\xagent.err.log"
    $process = Start-Process -FilePath $venvPython `
        -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", $HostName, "--port", $Port) `
        -WorkingDirectory $XAgentHome `
        -RedirectStandardOutput $logPath `
        -RedirectStandardError $errorLogPath `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -Path (Join-Path $XAgentHome "xagent.pid") -Value $process.Id
    Write-Step "PID $($process.Id) written to $(Join-Path $XAgentHome 'xagent.pid')"
}

function Install-Full {
    param([hashtable]$Python)
    Ensure-Source
    $compose = Test-DockerCompose
    if (-not $compose) { Fail "Docker Compose is required for full mode" }
    Merge-Secrets $Python
    Write-Step "Starting Docker Compose stack"
    Push-Location $SourceDir
    try {
        if ($compose -eq "docker compose") {
            docker compose --env-file $EnvFile up -d --build
        } else {
            docker-compose --env-file $EnvFile up -d --build
        }
    } finally {
        Pop-Location
    }
}

function Invoke-Check {
    $python = Find-Python
    Invoke-Python $python @("-c", "import sys; print('Python', sys.version.split()[0])")
    if (Test-DockerCompose) {
        Write-Step "Docker Compose detected"
    } else {
        Write-Step "Docker Compose not detected; lite mode remains available"
    }
    Write-Step "install.ps1 check passed"
}

if ($Check) {
    Invoke-Check
    exit 0
}

$python = Find-Python
New-Item -ItemType Directory -Force -Path $XAgentHome | Out-Null

if (-not $Mode) {
    $Mode = Read-Host "Install mode [lite/full] (default: lite)"
    if (-not $Mode) { $Mode = "lite" }
}

switch ($Mode) {
    "lite" {
        Write-BaseEnv
        $local = Get-LocalSource
        if ($local) { $SourceDir = $local }
        Merge-Secrets $python
        Install-Lite $python
        Start-Lite
    }
    "full" {
        Write-BaseEnv
        Install-Full $python
    }
}

Write-Step "X-Agent install completed"
Write-Step "Config: $EnvFile"
Write-Step "CLI shim: $(Join-Path $XAgentHome 'bin\xagent.cmd')"
