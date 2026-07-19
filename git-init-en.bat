@echo off
chcp 65001 >nul
REM X-Agent Quick Git Initialization Script

echo ==========================================
echo X-Agent Quick Git Initialization
echo ==========================================
echo.

echo [1/4] Initializing Git repository...
if not exist ".git" (
    git init
    git config user.name "X-Agent Developer"
    git config user.email "dev@xagent.ai"
    echo [OK] Git repository initialized
) else (
    echo [OK] Git repository already exists
)

echo.
echo [2/4] Adding files to Git...
git add .
echo [OK] Files added

echo.
echo [3/4] Creating initial commit...
git commit -m "Initial commit: X-Agent Core v0.1.0"
if errorlevel 1 (
    echo [INFO] No changes to commit
) else (
    echo [OK] Initial commit completed
)

echo.
echo [4/4] Showing Git status...
git status
echo.
git log --oneline -5

echo.
echo ==========================================
echo [OK] Git initialization completed!
echo ==========================================
echo.
echo Next steps:
echo   git checkout -b develop
echo   git remote add origin ^<your-repo-url^>
echo.

pause
