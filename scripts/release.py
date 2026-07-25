#!/usr/bin/env python3
"""X-Agent Release Automation.

Usage:
    python scripts/release.py --bump patch    # 0.3.0-alpha → 0.3.1-alpha
    python scripts/release.py --bump minor    # 0.3.0-alpha → 0.4.0-alpha
    python scripts/release.py --bump major    # 0.3.0-alpha → 1.0.0-alpha
    python scripts/release.py --release       # 0.3.0-alpha → 0.3.0 (remove -alpha)
    python scripts/release.py --check         # Validate release readiness
    python scripts/release.py --show          # Show current version
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
FRONTEND_PKG = ROOT / "frontend" / "package.json"

# Critical paths to scan for TODO/FIXME markers
CRITICAL_PATHS = [
    ROOT / "backend" / "app",
    ROOT / "cli",
]


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


def get_current_version() -> str:
    """Read version from pyproject.toml (single source of truth)."""
    content = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise RuntimeError("Cannot find version in pyproject.toml")
    return match.group(1)


def parse_version(version: str) -> tuple[int, int, int, str]:
    """Parse version string into (major, minor, patch, prerelease).

    Examples:
        '0.3.0-alpha' → (0, 3, 0, 'alpha')
        '1.2.3'       → (1, 2, 3, '')
        '2.0.0-rc.1'  → (2, 0, 0, 'rc.1')
    """
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", version)
    if not match:
        raise ValueError(f"Invalid version format: {version!r}")
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    prerelease = match.group(4) or ""
    return major, minor, patch, prerelease


def format_version(major: int, minor: int, patch: int, prerelease: str = "") -> str:
    """Format version components back into a string."""
    base = f"{major}.{minor}.{patch}"
    if prerelease:
        return f"{base}-{prerelease}"
    return base


def bump_version(version: str, bump_type: str) -> str:
    """Bump version according to type (patch/minor/major), preserving prerelease tag."""
    major, minor, patch, prerelease = parse_version(version)

    if bump_type == "patch":
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unknown bump type: {bump_type!r} (expected patch/minor/major)")

    return format_version(major, minor, patch, prerelease)


def make_release(version: str) -> str:
    """Remove prerelease suffix to make a stable release (e.g. 0.3.0-alpha → 0.3.0)."""
    major, minor, patch, _prerelease = parse_version(version)
    return format_version(major, minor, patch)


# ---------------------------------------------------------------------------
# Version update
# ---------------------------------------------------------------------------


def update_version(new_version: str, *, dry_run: bool = False) -> list[str]:
    """Update version in all locations. Returns list of updated files."""
    updated: list[str] = []

    # 1. pyproject.toml (single source of truth)
    content = PYPROJECT.read_text(encoding="utf-8")
    new_content = re.sub(
        r'^(version\s*=\s*")[^"]+(")',
        rf"\g<1>{new_version}\2",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if new_content != content:
        if not dry_run:
            PYPROJECT.write_text(new_content, encoding="utf-8")
        updated.append(str(PYPROJECT.relative_to(ROOT)))

    # 2. frontend/package.json (if version field exists)
    if FRONTEND_PKG.exists():
        pkg_data = json.loads(FRONTEND_PKG.read_text(encoding="utf-8"))
        if "version" in pkg_data:
            if not dry_run:
                pkg_data["version"] = new_version
                FRONTEND_PKG.write_text(
                    json.dumps(pkg_data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            updated.append(str(FRONTEND_PKG.relative_to(ROOT)))

    # 3. CHANGELOG.md — update the version reference in the header note
    if CHANGELOG.exists():
        changelog_text = CHANGELOG.read_text(encoding="utf-8")
        # Update the "当前为 **x.y.z**" reference
        new_changelog = re.sub(
            r"当前为 \*\*[^*]+\*\*",
            f"当前为 **{new_version}**",
            changelog_text,
        )
        if new_changelog != changelog_text:
            if not dry_run:
                CHANGELOG.write_text(new_changelog, encoding="utf-8")
            updated.append(str(CHANGELOG.relative_to(ROOT)))

    return updated


# ---------------------------------------------------------------------------
# Release readiness check
# ---------------------------------------------------------------------------


def check_release_readiness() -> list[str]:
    """Check if the project is ready for release. Returns list of issues found."""
    issues: list[str] = []
    version = get_current_version()
    _major, _minor, _patch, prerelease = parse_version(version)

    # 1. Check version is not -alpha/-dev/-rc for a stable release
    if prerelease:
        issues.append(
            f"[INFO] Version is '{version}' (prerelease: {prerelease}). "
            f"Use --release to strip prerelease tag for stable release."
        )

    # 2. Check CHANGELOG.md has entry for current version
    if CHANGELOG.exists():
        changelog_text = CHANGELOG.read_text(encoding="utf-8")
        if f"[{version}]" not in changelog_text:
            issues.append(
                f"[WARN] CHANGELOG.md has no entry for version [{version}]. "
                f"Add a '## [{version}] — <date>' section."
            )
    else:
        issues.append("[ERROR] CHANGELOG.md not found.")

    # 3. Check no TODO/FIXME in critical paths
    todo_count = 0
    for critical_dir in CRITICAL_PATHS:
        if not critical_dir.exists():
            continue
        for py_file in critical_dir.rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                todo_count += len(re.findall(r"\b(TODO|FIXME)\b", text))
            except OSError:
                pass
    if todo_count > 0:
        issues.append(
            f"[WARN] Found {todo_count} TODO/FIXME markers in critical paths "
            f"({', '.join(str(p.relative_to(ROOT)) for p in CRITICAL_PATHS if p.exists())})."
        )

    # 4. Suggest running tests
    issues.append(
        "[INFO] Run tests before release: "
        "python -m pytest tests/ -x -q --tb=short"
    )

    # 5. Check ruff clean
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--statistics", "backend/", "cli/"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            error_lines = result.stdout.strip().splitlines()
            summary = error_lines[-1] if error_lines else "unknown errors"
            issues.append(f"[WARN] ruff check reports issues: {summary}")
        else:
            issues.append("[OK] ruff check passed (backend/, cli/).")
    except FileNotFoundError:
        issues.append("[INFO] ruff not installed; skipping lint check.")
    except subprocess.TimeoutExpired:
        issues.append("[INFO] ruff check timed out; skipping.")

    # 6. Check git status is clean
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            dirty_count = len(result.stdout.strip().splitlines())
            issues.append(
                f"[WARN] Working tree has {dirty_count} uncommitted change(s). "
                f"Commit before tagging a release."
            )
        elif result.returncode == 0:
            issues.append("[OK] Working tree is clean.")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        issues.append("[INFO] git not available; skipping clean-tree check.")

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="X-Agent Release Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--bump",
        choices=["patch", "minor", "major"],
        help="Bump version (preserves prerelease tag)",
    )
    group.add_argument(
        "--release",
        action="store_true",
        help="Strip prerelease tag to make a stable release",
    )
    group.add_argument(
        "--check",
        action="store_true",
        help="Validate release readiness (no changes made)",
    )
    group.add_argument(
        "--show",
        action="store_true",
        help="Show current version",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without writing files",
    )

    args = parser.parse_args()

    if args.show:
        print(get_current_version())
        return 0

    if args.check:
        print(f"Release readiness check for version {get_current_version()}:\n")
        issues = check_release_readiness()
        for issue in issues:
            print(f"  {issue}")
        errors = [i for i in issues if i.startswith("[ERROR]")]
        if errors:
            print(f"\n❌ {len(errors)} error(s) found. Fix before releasing.")
            return 1
        print("\n✅ Readiness check complete.")
        return 0

    current = get_current_version()

    if args.bump:
        new_version = bump_version(current, args.bump)
    elif args.release:
        new_version = make_release(current)
    else:
        parser.print_help()
        return 1

    print(f"Version: {current} → {new_version}")

    if args.dry_run:
        print("(dry-run: no files will be modified)")
        updated = update_version(new_version, dry_run=True)
    else:
        updated = update_version(new_version)

    if updated:
        print(f"Updated files:")
        for f in updated:
            print(f"  - {f}")
    else:
        print("No files needed updating.")

    if not args.dry_run:
        print(f"\nNext steps:")
        print(f"  1. Review changes: git diff")
        print(f"  2. Commit: git commit -am 'release: v{new_version}'")
        print(f"  3. Tag: git tag v{new_version}")
        print(f"  4. Push: git push origin main --tags")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
