@echo off
chcp 65001 >nul
REM X-Agent Git Commit Script

echo ==========================================
echo X-Agent Git Commit
echo ==========================================
echo.

echo [1/4] Adding all files to Git...
git add .
if errorlevel 1 (
    echo [ERROR] Failed to add files
    pause
    exit /b 1
)
echo [OK] All files added

echo.
echo [2/4] Creating initial commit...
git commit -m "Initial commit: X-Agent Core v0.1.0" -m "" -m "- 完成第一阶段安全加固（9项CRITICAL漏洞已修复）" -m "- 实现7个核心功能系统" -m "- 注册38个API路由器" -m "- 包含90+测试文件" -m "- 安全状态：从CRITICAL降低到LOW风险" -m "" -m "核心功能：" -m "- 认证授权系统（bcrypt + JWT）" -m "- RBAC权限控制" -m "- 上下文管理系统" -m "- 多代理并行执行" -m "- 浏览器自动化" -m "- 记忆系统优化" -m "- 工具并行调用"
if errorlevel 1 (
    echo [ERROR] Commit failed
    pause
    exit /b 1
)
echo [OK] Initial commit completed

echo.
echo [3/4] Viewing commit history...
git log --oneline -5

echo.
echo [4/4] Creating develop branch...
git checkout -b develop
if errorlevel 1 (
    echo [WARN] Failed to create develop branch (may already exist)
) else (
    echo [OK] Develop branch created and checked out
)

echo.
echo ==========================================
echo [OK] Git commit completed!
echo ==========================================
echo.
echo Current branch:
git branch
echo.
echo Next steps:
echo   git remote add origin ^<your-repo-url^>
echo   git push -u origin master
echo   git push -u origin develop
echo.

pause
