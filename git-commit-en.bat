@echo off
chcp 65001 >nul
REM X-Agent Git Commit Script - English Version

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
git commit -m "Initial commit: X-Agent Core v0.1.0" -m "" -m "Security Hardening (Phase 1 Complete):" -m "- Fixed 9 CRITICAL security vulnerabilities" -m "- Implemented bcrypt + JWT authentication" -m "- Added RBAC authorization system" -m "- Implemented path sandbox isolation" -m "- Added rate limiting and account lockout" -m "" -m "Core Features (7 Systems):" -m "- Context management system" -m "- Multi-agent parallel execution" -m "- Browser automation enhancement" -m "- Filesystem refactoring" -m "- Parallel tool execution" -m "- Memory system optimization" -m "- User experience improvements" -m "" -m "Infrastructure:" -m "- 38 API routers registered" -m "- 90+ test files" -m "- Security status: CRITICAL -> LOW risk"
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
    git checkout develop
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
echo Repository status:
git status --short
echo.
echo Next steps:
echo   git remote add origin ^<your-repo-url^>
echo   git push -u origin master
echo   git push -u origin develop
echo.

pause
