#!/usr/bin/env python3
"""Deployment & secret hardening gate for X-Agent.

This script is the durable enforcement layer behind the deployment/secret
defenses. It scans deployment manifests (docker-compose, k8s, helm),
shell deploy scripts, and the committed ``.env.example`` for production
risks and refuses to pass (exit code 1) when any HIGH severity issue is
found.

It is wired into ``.pre-commit-config.yaml`` (``deployment-hardening-gate``)
and exercised by ``tests/test_deployment_hardening.py`` and
``tests/test_production_hardening_gate.py``.

Checks
------
1. Weak / default passwords baked into manifests (admin, password, changeme,
   minioadmin, ``POSTGRES_PASSWORD: xagent`` ...).
2. Mutable ``:latest`` image tags.
3. Production ``--reload`` (uvicorn autoreload must never ship to prod).
4. Publicly bound database/broker ports (``0.0.0.0:5432`` style).
5. Plausible real secrets committed in config (e.g. ``sk-...`` keys,
   long high-entropy values assigned to password/secret/token keys).
6. ``.env.example`` must not ship usable secret values.

Usage
-----
    python scripts/security_deployment_gate.py            # scan whole repo
    python scripts/security_deployment_gate.py file1 ...  # scan given files

Designed to be import-safe: tests call :func:`scan_paths` /
:func:`scan_text` directly without triggering ``sys.exit``.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent

# Severity ranking for reporting / gating.
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


@dataclass(frozen=True)
class Finding:
    """A single deployment-hardening issue."""

    severity: str  # HIGH | MEDIUM | LOW
    rule: str
    file: str
    line: int
    message: str
    snippet: str = ""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        loc = f"{self.file}:{self.line}" if self.line else self.file
        out = f"[{self.severity}] {self.rule} — {loc}: {self.message}"
        if self.snippet:
            out += f"\n      {self.snippet.strip()}"
        return out


# --- Patterns -------------------------------------------------------------

# Weak/default password values that must never be baked into a manifest.
_WEAK_PASSWORD_VALUES = {
    "admin",
    "password",
    "passwd",
    "changeme",
    "change-me",
    "secret",
    "root",
    "test",
    "postgres",
    "redis",
    "xagent",
    "xagent123",
    "minioadmin",
    "neo4j",
    "guest",
    "123456",
}

# Keys whose value is a credential. Note ``[A-Z0-9_]*`` (not ``[A-Z_]*``) so
# digit-bearing prefixes like ``NEO4J_PASSWORD`` are matched.
_PASSWORD_KEY_RE = re.compile(
    r"""(?ix)
    \b(
        [A-Z0-9_]*PASSWORD |
        [A-Z0-9_]*PASSWD |
        [A-Z0-9_]*SECRET(?:_KEY)? |
        [A-Z0-9_]*ACCESS_KEY |
        MINIO_(?:ACCESS|SECRET)_KEY |
        GF_SECURITY_ADMIN_PASSWORD
    )
    \s*[:=]\s*
    (?P<q>["']?)(?P<val>[^"'\s#$}{]+)(?P=q)
    """
)

# An env-substitution value like ${FOO}, ${FOO:?...}, ${FOO:-default} is NOT a
# hardcoded secret (the default branch is handled separately).
_ENV_SUBST_RE = re.compile(r"\$\{[^}]+\}")

# Weak default *inside* a substitution, captured together with the variable
# name, e.g. ${GRAFANA_PASSWORD:-admin}. The ":-" / ":=" form supplies a
# baked-in fallback that ships if the env var is unset — so a weak fallback on
# a *credential* variable is still a weak default password. The variable name
# (not the surrounding line) decides whether it is a credential, so username /
# database-name fallbacks such as ${DB_USER:-postgres} are not misjudged.
_ENV_DEFAULT_WITH_VAR_RE = re.compile(
    r"\$\{(?P<var>[A-Za-z0-9_]+):[-=](?P<val>[^}]*)\}"
)


def _is_credential_var(name: str) -> bool:
    """True if an env variable name denotes a secret/password/credential.

    Usernames and database/identifier names are explicitly excluded: a weak
    *username* (``neo4j``, ``postgres``, ``admin``) is an identity, not a
    secret, and must not be gated as a HIGH deployment risk.
    """
    up = name.upper()
    if (
        up.endswith("_USER")
        or up.endswith("_USERNAME")
        or up.endswith("_USERS")
        or up == "USER"
        or up == "USERNAME"
        or up.endswith("_NAME")
        or up.endswith("_DB")
        or up.endswith("_DATABASE")
    ):
        return False
    return bool(re.search(r"(PASSWORD|PASSWD|SECRET|TOKEN|ACCESS_KEY|API_KEY|_KEY|APIKEY)", up))

# Mutable image tag.
_LATEST_IMAGE_RE = re.compile(r"""(?ix)\bimage\s*[:=]\s*["']?([^\s"']+:latest)\b""")
_IMAGE_NO_TAG_RE = re.compile(r"""(?ix)^\s*image\s*:\s*["']?([A-Za-z0-9._/\-]+)["']?\s*$""")

# uvicorn / hypercorn autoreload.
_RELOAD_RE = re.compile(r"--reload\b")

# Publicly bound DB / broker ports.
_DB_PORTS = {"5432", "6379", "7687", "27017", "3306", "9200", "5672", "9000"}
_PUBLIC_PORT_RE = re.compile(r"""["']?0\.0\.0\.0:(?P<port>\d+):(?P<cport>\d+)["']?""")

# Plausible real provider secrets.
_REAL_SECRET_RES = [
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"), "OpenAI-style API key"),
    (re.compile(r"\bsk-proj-[A-Za-z0-9]{16,}\b"), "OpenAI project key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "GitHub PAT"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"), "Google API key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "Private key"),
]

# Allowlisted substrings that mark a value as an intentional placeholder.
_PLACEHOLDER_MARKERS = (
    "your-",
    "your_",
    "example",
    "replace",
    "<",
    "xxxx",
    "...",
    "${",
)


def _is_placeholder(value: str) -> bool:
    low = value.lower()
    return any(marker in low for marker in _PLACEHOLDER_MARKERS)


def _looks_like_env_required(line: str) -> bool:
    """True if the line uses required/explicit env substitution for its value."""
    return bool(_ENV_SUBST_RE.search(line))


# --- Core scanning --------------------------------------------------------


def scan_text(text: str, *, filename: str = "<string>") -> list[Finding]:
    """Scan a single file's text content and return findings.

    Pure function (no filesystem / exit) so tests can call it directly.
    """
    findings: list[Finding] = []
    is_env_example = filename.endswith(".env.example")

    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # 1) Weak/default password values.
        for m in _PASSWORD_KEY_RE.finditer(line):
            val = m.group("val")
            if not val or _looks_like_env_required(line) or _is_placeholder(val):
                continue
            if val.lower() in _WEAK_PASSWORD_VALUES:
                findings.append(
                    Finding(
                        "HIGH",
                        "weak-default-password",
                        filename,
                        idx,
                        f"weak/default credential value '{val}' is hardcoded",
                        stripped,
                    )
                )

        # 1b) Weak default baked into a ${VAR:-default} substitution. The
        # fallback ships when the env var is unset. Whether it is a HIGH risk
        # is decided by the *substitution variable's own name* — so a weak
        # password fallback (${X_PASSWORD:-admin}) is flagged, while a weak
        # username/db-name fallback (${DB_USER:-postgres}) is not, even when
        # both appear on the same NEO4J_AUTH-style line.
        for m in _ENV_DEFAULT_WITH_VAR_RE.finditer(line):
            var_name = m.group("var") or ""
            default_val = (m.group("val") or "").strip().strip("\"'")
            if not default_val or not _is_credential_var(var_name):
                continue
            if default_val.lower() in _WEAK_PASSWORD_VALUES:
                findings.append(
                    Finding(
                        "HIGH",
                        "weak-default-password",
                        filename,
                        idx,
                        f"weak fallback default '{default_val}' in env substitution ${{{var_name}}}",
                        stripped,
                    )
                )

        # 2) :latest image tags.
        if _LATEST_IMAGE_RE.search(line):
            findings.append(
                Finding(
                    "HIGH",
                    "mutable-latest-image",
                    filename,
                    idx,
                    "image uses mutable ':latest' tag; pin an explicit version",
                    stripped,
                )
            )

        # 3) production --reload.
        if _RELOAD_RE.search(line) and not _looks_like_env_required(line):
            findings.append(
                Finding(
                    "HIGH",
                    "uvicorn-reload",
                    filename,
                    idx,
                    "--reload must never be hardcoded (autoreload is dev-only)",
                    stripped,
                )
            )

        # 4) Public DB/broker port bindings.
        for m in _PUBLIC_PORT_RE.finditer(line):
            if m.group("cport") in _DB_PORTS or m.group("port") in _DB_PORTS:
                findings.append(
                    Finding(
                        "HIGH",
                        "public-db-port",
                        filename,
                        idx,
                        f"database/broker port {m.group('cport')} bound to 0.0.0.0 "
                        "(publicly exposed)",
                        stripped,
                    )
                )

        # 5) Real provider secrets committed.
        for rx, label in _REAL_SECRET_RES:
            if rx.search(line):
                findings.append(
                    Finding(
                        "HIGH",
                        "hardcoded-secret",
                        filename,
                        idx,
                        f"possible committed credential ({label})",
                        stripped,
                    )
                )

        # 6) .env.example must not ship usable secret values.
        if is_env_example:
            mm = re.match(r"\s*([A-Z0-9_]*(?:PASSWORD|SECRET|KEY|TOKEN))\s*=\s*(\S+)", line)
            if mm:
                val = mm.group(2)
                if not _is_placeholder(val) and not val.startswith("${"):
                    # Allow obviously safe non-secret defaults (booleans, hosts).
                    if val.lower() not in {"true", "false", "info", "debug", "warn"}:
                        findings.append(
                            Finding(
                                "MEDIUM",
                                "env-example-value",
                                filename,
                                idx,
                                f"{mm.group(1)} should be empty/placeholder in .env.example",
                                stripped,
                            )
                        )

    return findings


def iter_default_targets(root: Path) -> list[Path]:
    """Return the default set of files this gate scans under ``root``."""
    targets: list[Path] = []
    patterns = [
        "docker-compose*.yml",
        "docker-compose*.yaml",
        ".env.example",
    ]
    for pat in patterns:
        targets.extend(root.glob(pat))
    for sub in ("deployment", "monitoring", "templates"):
        base = root / sub
        if not base.exists():
            continue
        for ext in ("*.yml", "*.yaml", "*.sh"):
            targets.extend(base.rglob(ext))
    # De-dup, stable order, skip vendored / cache dirs.
    seen: set[Path] = set()
    out: list[Path] = []
    skip_parts = {".git", "node_modules", ".venv", "venv", "__pycache__"}
    for p in sorted(targets):
        if p in seen or any(part in skip_parts for part in p.parts):
            continue
        seen.add(p)
        out.append(p)
    return out


def scan_paths(paths: Iterable[Path], *, root: Path | None = None) -> list[Finding]:
    """Scan an explicit list of files."""
    root = root or REPO_ROOT
    findings: list[Finding] = []
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except (OSError, IsADirectoryError):
            continue
        try:
            rel = str(Path(path).resolve().relative_to(root))
        except ValueError:
            rel = str(path)
        findings.extend(scan_text(text, filename=rel.replace("\\", "/")))
    return findings


def scan_repo(root: Path | None = None) -> list[Finding]:
    """Scan all default deployment/secret targets under ``root``."""
    root = root or REPO_ROOT
    return scan_paths(iter_default_targets(root), root=root)


def _sort_key(f: Finding) -> tuple[int, str, int]:
    return (SEVERITY_ORDER.get(f.severity, 9), f.file, f.line)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        findings = scan_paths([Path(a) for a in argv])
    else:
        findings = scan_repo()

    findings.sort(key=_sort_key)
    high = [f for f in findings if f.severity == "HIGH"]
    medium = [f for f in findings if f.severity == "MEDIUM"]

    print("=" * 70)
    print("X-Agent Deployment Hardening Gate")
    print("=" * 70)
    if not findings:
        print("OK No deployment-hardening issues found.")
        return 0

    print(f"Found {len(findings)} issue(s): {len(high)} HIGH, {len(medium)} MEDIUM")
    print("-" * 70)
    for f in findings:
        print(str(f))
    print("-" * 70)

    # Gate fails on any HIGH severity finding.
    if high:
        print("FAIL: HIGH severity deployment risks must be fixed before commit.")
        return 1
    print("WARN: only non-blocking issues found.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
