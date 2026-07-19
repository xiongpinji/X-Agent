# M2 全量测试基线筛选脚本
# 用法: .env\Scripts\Activate.ps1; .\scriptsun_baseline.ps1
# 输出: m2_baseline_results.log (仅 FAILED 名单)

$env:XAGENT_QDRANT_URL = ""
$env:PYTHONDONTWRITEBYTECODE = "1"

# 重型目录排除（会卡死/timeout 拦不住）
$ignoreDirs = @(
    "tests/e2e",
    "tests/performance",
    "tests/enterprise/performance"
)

$ignoreArgs = $ignoreDirs | ForEach-Object { "--ignore=$_" }

Write-Host "=== 收集测试 ===" -ForegroundColor Cyan
pytest tests/ `
  @ignoreArgs `
  --collect-only -q `
  -o addopts="" -p no:cov -p no:cacheprovider `
  2>&1 | Select-String "test collected"

Write-Host "=== 开始全量跑 (可能需要 30-60 分钟) ===" -ForegroundColor Cyan
pytest tests/ `
  @ignoreArgs `
  -o addopts="" -p no:cov -p no:cacheprovider `
  --no-header -q --tb=line `
  2>&1 | Tee-Object -FilePath m2_baseline_results.log

Write-Host "=== FAILED 汇总 ===" -ForegroundColor Red
Select-String -Path m2_baseline_results.log -Pattern "FAILED"
