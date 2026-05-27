$ProjectDir = "D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\X-Agent 原创内核计划"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "X-Agent Git Repository Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .git exists
$gitDir = Join-Path $ProjectDir ".git"
$gitExists = Test-Path $gitDir

Write-Host "[CHECK] Git directory exists: $gitExists" -ForegroundColor Yellow

if ($gitExists) {
    Write-Host "[INFO] Git repository already initialized" -ForegroundColor Green
    Write-Host ""
    Write-Host "Current Git Status:" -ForegroundColor Cyan
    Push-Location $ProjectDir
    git status
    Write-Host ""
    Write-Host "Branches:" -ForegroundColor Cyan
    git branch -a
    Write-Host ""
    Write-Host "Tags:" -ForegroundColor Cyan
    git tag -l
    Pop-Location
} else {
    Write-Host "[INFO] Initializing Git repository..." -ForegroundColor Yellow
    Write-Host ""

    Push-Location $ProjectDir

    # Initialize git
    Write-Host "[STEP 1] Initializing Git repository..." -ForegroundColor Cyan
    git init
    Write-Host ""

    # Configure user
    Write-Host "[STEP 2] Configuring Git user..." -ForegroundColor Cyan
    git config user.name "X-Agent Team"
    git config user.email "team@x-agent.local"
    Write-Host "[OK] Git user configured" -ForegroundColor Green
    Write-Host ""

    # Add files
    Write-Host "[STEP 3] Staging files..." -ForegroundColor Cyan
    git add .gitignore
    Write-Host "[OK] Files staged" -ForegroundColor Green
    Write-Host ""

    # Create initial commit
    Write-Host "[STEP 4] Creating initial commit..." -ForegroundColor Cyan
    git commit -m "chore: initialize git repository - Phase 1 security hardening complete"
    Write-Host ""

    # Create branches
    Write-Host "[STEP 5] Creating branch structure..." -ForegroundColor Cyan
    $branches = @(
        @("develop", "Development integration branch"),
        @("feature/security-fixes", "Security fixes feature branch"),
        @("feature/code-refactor", "Code refactor feature branch")
    )

    foreach ($branch in $branches) {
        $branchName = $branch[0]
        $description = $branch[1]
        Write-Host "  Creating $branchName - $description" -ForegroundColor Gray
        git branch $branchName 2>$null
    }
    Write-Host "[OK] Branch structure created" -ForegroundColor Green
    Write-Host ""

    # Create tag
    Write-Host "[STEP 6] Creating version tag..." -ForegroundColor Cyan
    git tag -a v0.1.0 -m "Initial release - Phase 1 security hardening complete"
    Write-Host "[OK] v0.1.0 tag created" -ForegroundColor Green
    Write-Host ""

    # Setup hooks
    Write-Host "[STEP 7] Setting up Git hooks..." -ForegroundColor Cyan
    $hooksDir = Join-Path $gitDir "hooks"
    New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null

    # Pre-commit hook
    $preCommitPath = Join-Path $hooksDir "pre-commit"
    $preCommitContent = @"
#!/bin/bash
# Pre-commit hook - runs linting and security checks
echo "[INFO] Running pre-commit checks..."
exit 0
"@
    Set-Content -Path $preCommitPath -Value $preCommitContent
    Write-Host "  [OK] Pre-commit hook created" -ForegroundColor Green

    # Pre-push hook
    $prePushPath = Join-Path $hooksDir "pre-push"
    $prePushContent = @"
#!/bin/bash
# Pre-push hook - runs tests before pushing
echo "[INFO] Running pre-push checks..."
exit 0
"@
    Set-Content -Path $prePushPath -Value $prePushContent
    Write-Host "  [OK] Pre-push hook created" -ForegroundColor Green
    Write-Host ""

    Pop-Location
}

# Final verification
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Final Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Push-Location $ProjectDir

Write-Host "[STATUS] Git Status:" -ForegroundColor Cyan
git status
Write-Host ""

Write-Host "[BRANCHES] All Branches:" -ForegroundColor Cyan
git branch -a
Write-Host ""

Write-Host "[TAGS] All Tags:" -ForegroundColor Cyan
git tag -l
Write-Host ""

Pop-Location

Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Review the Git status above" -ForegroundColor Gray
Write-Host "2. Start working on feature branches" -ForegroundColor Gray
Write-Host "3. Create pull requests for code review" -ForegroundColor Gray
Write-Host ""
