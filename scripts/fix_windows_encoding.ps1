# ============================================================================
# X-Agent Windows 中文路径编码修复脚本
# ----------------------------------------------------------------------------
# 问题: Windows 中文路径下 Python site 模块因 GBK 解码失败而无法启动
# 解决: 设置系统级 PYTHONUTF8=1 环境变量
#
# 使用方法 (以管理员身份运行 PowerShell):
#   .\scripts\fix_windows_encoding.ps1
#
# 或手动设置:
#   [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
# ============================================================================

param(
    [switch]$SystemWide  # 设置为系统级变量(需要管理员权限)
)

$ErrorActionPreference = "Stop"

Write-Host "X-Agent Windows 编码修复工具" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

# 检查当前 Python 版本
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "[OK] Python 已安装: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] 未找到 Python，请先安装 Python 3.7+" -ForegroundColor Red
    exit 1
}

# 设置 PYTHONUTF8 环境变量
$target = if ($SystemWide) { "Machine" } else { "User" }

try {
    if ($SystemWide) {
        # 需要管理员权限
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        if (-not $isAdmin) {
            Write-Host "[WARN] 设置系统级变量需要管理员权限，将改为用户级" -ForegroundColor Yellow
            $target = "User"
        }
    }

    [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", $target)
    Write-Host "[OK] 已设置 PYTHONUTF8=1 ($target 级别)" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] 设置环境变量失败: $_" -ForegroundColor Red
    exit 1
}

# 同时设置 PYTHONIOENCODING 作为备用
try {
    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", $target)
    Write-Host "[OK] 已设置 PYTHONIOENCODING=utf-8 ($target 级别)" -ForegroundColor Green
} catch {
    Write-Host "[WARN] 设置 PYTHONIOENCODING 失败(非关键): $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "验证修复:" -ForegroundColor Cyan
Write-Host "  1. 关闭并重新打开终端"
Write-Host "  2. 运行: python -c \"import sys; print(sys.flags.utf8_mode)\""
Write-Host "  3. 输出应为 1"
Write-Host ""
Write-Host "如果问题仍然存在，请尝试:" -ForegroundColor Yellow
Write-Host "  - 使用 python -X utf8 运行脚本"
Write-Host "  - 或将项目移动到纯英文路径"
Write-Host ""
Write-Host "修复完成!" -ForegroundColor Green
