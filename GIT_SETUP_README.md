# Git Normalization Setup Guide

This directory contains scripts to set up Git Flow workflow and clean up sensitive information from the X-Agent project.

## Files

- **git_normalization.py**: Main setup script that initializes Git Flow
- **cleanup_sensitive_info.py**: Script to remove sensitive files from Git history
- **setup_git_flow.bat**: Windows batch script alternative (legacy)
- **docs/git-workflow.md**: Complete Git workflow documentation

## Quick Start

### 1. Initialize Git Flow

Run the main setup script:

```bash
python git_normalization.py
```

This will:
- Initialize Git repository (if not already initialized)
- Configure Git user (local)
- Create initial commit
- Create branch structure (develop, feature/security-fixes, feature/code-refactor)
- Create version tag v0.1.0
- Setup Git hooks (pre-commit, pre-push)

### 2. Verify Setup

After running the script, verify the setup:

```bash
# Check branches
git branch -a

# Check tags
git tag -l

# Check hooks
ls -la .git/hooks/
```

### 3. Clean Sensitive Information (Optional)

If you need to remove sensitive files from Git history:

```bash
python cleanup_sensitive_info.py
```

**WARNING**: This operation:
- Rewrites Git history
- Requires all team members to re-clone the repository
- Should only be done if sensitive data was accidentally committed

Before running:
1. Backup your local changes
2. Ensure no one is actively working on the repository
3. Notify team members

## Branch Structure

```
main (production)
├── develop (integration)
│   ├── feature/security-fixes
│   └── feature/code-refactor
└── release/* (release branches)
```

## Workflow

### Starting a Feature

```bash
# Update develop
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat(scope): description"

# Push to remote
git push -u origin feature/your-feature-name
```

### Creating a Pull Request

1. Push your feature branch
2. Create PR against `develop` branch
3. Ensure all checks pass
4. Request code review
5. Merge when approved

## Git Hooks

### Pre-commit Hook

Runs before each commit:
- Ruff linting check
- Sensitive information detection

### Pre-push Hook

Runs before pushing:
- Test suite execution
- Ensures code quality before pushing

## Sensitive Information

The following files are protected:
- `data/api_keys.json`
- `data/workflows.json`
- `data/approvals.json`
- `x_agent_core.egg-info/`

These are added to `.gitignore` and should never be committed.

## Troubleshooting

### Git not found

Ensure Git is installed and in your PATH:

```bash
git --version
```

### Hooks not executing

On Windows, hooks may need to be in `.bat` format. The setup script creates bash hooks for Unix-like systems.

### Permission denied on hooks

Make hooks executable:

```bash
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/pre-push
```

### Cleanup failed

If `cleanup_sensitive_info.py` fails:

1. Ensure `git filter-repo` is installed:
   ```bash
   pip install git-filter-repo
   ```

2. Check the backup directory created during cleanup

3. Restore from backup if needed:
   ```bash
   rm -rf .git
   cp -r .git.backup.YYYYMMDD_HHMMSS .git
   ```

## Documentation

For complete Git workflow guidelines, see `docs/git-workflow.md`

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review `docs/git-workflow.md`
3. Contact the X-Agent team
