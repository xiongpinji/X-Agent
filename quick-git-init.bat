@echo off
REM X-Agent 快速Git初始化脚本
REM 最小化版本 - 只执行核心步骤

echo ==========================================
echo X-Agent 快速Git初始化
echo ==========================================
echo.

echo [1/4] 初始化Git仓库...
if not exist ".git" (
    git init
    git config user.name "X-Agent Developer"
    git config user.email "dev@xagent.ai"
    echo [OK] Git仓库已初始化
) else (
    echo [OK] Git仓库已存在
)

echo.
echo [2/4] 添加文件到Git...
git add .
echo [OK] 文件已添加

echo.
echo [3/4] 创建初始提交...
git commit -m "Initial commit: X-Agent Core v0.1.0"
if errorlevel 1 (
    echo [INFO] 没有需要提交的更改
) else (
    echo [OK] 初始提交完成
)

echo.
echo [4/4] 显示Git状态...
git status
git log --oneline -5

echo.
echo ==========================================
echo [OK] Git初始化完成！
echo ==========================================
echo.
echo 下一步：
echo   git checkout -b develop
echo   git remote add origin ^<your-repo-url^>
echo.

pause
