# Git Workflow Guide

## Branch Strategy (Git Flow)

### Main Branches

- **main**: Production-ready code. Only receives merges from release branches.
- **develop**: Integration branch for features. Base for all feature branches.

### Supporting Branches

- **feature/\***: Feature development branches
  - Created from: `develop`
  - Merged back into: `develop`
  - Naming: `feature/feature-name` or `feature/security-fixes`, `feature/code-refactor`

- **release/\***: Release preparation branches
  - Created from: `develop`
  - Merged into: `main` and back to `develop`
  - Naming: `release/v1.0.0`

- **hotfix/\***: Production bug fixes
  - Created from: `main`
  - Merged into: `main` and `develop`
  - Naming: `hotfix/issue-description`

## Commit Message Convention

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that don't affect code meaning (formatting, missing semicolons, etc.)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **chore**: Changes to build process, dependencies, or tooling

### Examples
```
feat(memory): add vector similarity search
fix(auth): resolve token expiration issue
docs(api): update endpoint documentation
refactor(core): simplify agent loop logic
```

## Workflow Steps

### Starting a Feature

```bash
# Update develop branch
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

1. Push your feature branch to remote
2. Create PR against `develop` branch
3. Ensure all checks pass (tests, linting, security)
4. Request code review
5. Address review comments
6. Merge when approved

### Merging to Develop

```bash
# Ensure branch is up to date
git fetch origin
git rebase origin/develop

# Merge via PR (preferred) or locally
git checkout develop
git pull origin develop
git merge --no-ff feature/your-feature-name
git push origin develop
```

### Release Process

```bash
# Create release branch
git checkout -b release/v1.0.0 develop

# Update version numbers, changelog
git commit -m "chore(release): bump version to v1.0.0"

# Merge to main
git checkout main
git pull origin main
git merge --no-ff release/v1.0.0
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin main --tags

# Merge back to develop
git checkout develop
git merge --no-ff release/v1.0.0
git push origin develop

# Delete release branch
git branch -d release/v1.0.0
git push origin --delete release/v1.0.0
```

## Pre-commit Hooks

The project includes pre-commit hooks to ensure code quality:

- **ruff check**: Linting and code style validation
- **Sensitive info check**: Prevents committing API keys, tokens, etc.

Hooks are automatically run before each commit. To bypass (not recommended):
```bash
git commit --no-verify
```

## Pre-push Hooks

Before pushing, the following checks run:

- **Test suite**: All tests must pass
- **Security checks**: Verify no sensitive data is being pushed

## Sensitive Information

Never commit:
- API keys or tokens
- Database credentials
- Private keys
- Passwords or secrets

Use `.env` files (added to .gitignore) for local configuration.

## Tagging

Create annotated tags for releases:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

Tag format: `v<major>.<minor>.<patch>`

## Cleanup

Delete local branches after merging:

```bash
git branch -d feature/your-feature-name
```

Delete remote branches:

```bash
git push origin --delete feature/your-feature-name
```

## Troubleshooting

### Accidentally committed sensitive data

If you accidentally committed sensitive data:

1. Remove the file from Git history using `git filter-repo`
2. Update .gitignore
3. Force push (only if not yet pushed to shared remote)

### Merge conflicts

```bash
# Resolve conflicts in your editor
git add <resolved-files>
git commit -m "fix: resolve merge conflicts"
git push
```

### Revert a commit

```bash
# Create a new commit that undoes changes
git revert <commit-hash>

# Or reset (only for unpushed commits)
git reset --soft HEAD~1
```

## Best Practices

1. Keep commits small and focused
2. Write clear, descriptive commit messages
3. Pull before pushing to avoid conflicts
4. Use feature branches for all work
5. Never force push to shared branches
6. Review your own code before requesting review
7. Keep branches up to date with develop
8. Delete merged branches to keep repository clean
