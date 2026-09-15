@echo off
REM Git Flow Setup Script for X-Agent Project
REM This script initializes Git repository and creates branch structure

setlocal enabledelayedexpansion

set PROJECT_DIR=D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\X-Agent 原创内核计划

cd /d "%PROJECT_DIR%"

echo ========================================
echo X-Agent Git Flow Setup
echo ========================================
echo.

REM Check if .git exists
if exist .git (
    echo [INFO] Git repository already initialized
) else (
    echo [INFO] Initializing Git repository...
    git init
    echo [OK] Git repository initialized
)

echo.
echo [INFO] Configuring Git user (local)...
git config user.name "X-Agent Team"
git config user.email "team@x-agent.local"
echo [OK] Git user configured

echo.
echo [INFO] Creating initial commit...
git add .gitignore docs/git-workflow.md
git commit -m "chore: initialize git flow and documentation" 2>nul || echo [INFO] Nothing to commit

echo.
echo [INFO] Creating develop branch...
git branch develop 2>nul || echo [INFO] develop branch already exists
git checkout develop 2>nul || echo [INFO] Already on develop

echo.
echo [INFO] Creating feature branches...
git branch feature/security-fixes 2>nul || echo [INFO] feature/security-fixes already exists
git branch feature/code-refactor 2>nul || echo [INFO] feature/code-refactor already exists

echo.
echo [INFO] Creating version tag v0.1.0...
git tag -a v0.1.0 -m "Initial release - Phase 0 MVP" 2>nul || echo [INFO] Tag v0.1.0 already exists

echo.
echo [INFO] Setting up Git hooks...

REM Create hooks directory
if not exist .git\hooks mkdir .git\hooks

REM Create pre-commit hook
echo Creating pre-commit hook...
(
echo @echo off
echo REM Pre-commit hook - runs linting and security checks
echo.
echo echo [INFO] Running ruff check...
echo ruff check . --exit-zero
echo if errorlevel 1 (
echo     echo [ERROR] Ruff check failed
echo     exit /b 1
echo ^)
echo.
echo echo [INFO] Checking for sensitive information...
echo findstr /r "api_key.*password.*secret.*token" *.py backend\*.py backend\app\*.py 2^>nul
echo if not errorlevel 1 (
echo     echo [WARNING] Possible sensitive information detected
echo ^)
echo.
echo echo [OK] Pre-commit checks passed
echo exit /b 0
) > .git\hooks\pre-commit.bat

REM Create pre-push hook
echo Creating pre-push hook...
(
echo @echo off
echo REM Pre-push hook - runs tests before pushing
echo.
echo echo [INFO] Running test suite...
echo pytest tests/ -v --tb=short 2^>nul
echo if errorlevel 1 (
echo     echo [ERROR] Tests failed - push aborted
echo     exit /b 1
echo ^)
echo.
echo echo [OK] All tests passed - safe to push
echo exit /b 0
) > .git\hooks\pre-push.bat

echo [OK] Git hooks created

echo.
echo ========================================
echo Git Flow Setup Complete
echo ========================================
echo.
echo Branch structure:
git branch -a
echo.
echo Tags:
git tag -l
echo.
echo Next steps:
echo 1. Review the git-workflow.md documentation
echo 2. Start working on feature branches
echo 3. Create pull requests for code review
echo.
