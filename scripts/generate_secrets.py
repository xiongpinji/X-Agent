#!/usr/bin/env python3
"""Generate secure X-Agent secrets and merge them into .env files.

The installer uses this module to create a local ``.env`` without clobbering
operator-supplied values. Existing non-empty entries are preserved; missing or
blank required keys are filled.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import string
import sys
from pathlib import Path

REQUIRED_SECRET_KEYS = (
    "JWT_SECRET",
    "ENCRYPTION_KEY",
    "AUDIT_HMAC_SECRET",
    "BOOTSTRAP_API_KEY",
)
OPTIONAL_SECRET_KEYS = (
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "NEO4J_PASSWORD",
    "DB_PASSWORD",
    "REDIS_PASSWORD",
    "QDRANT_API_KEY",
)
UNPREFIXED_ENV_KEYS = frozenset(
    {
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "NEO4J_PASSWORD",
        "DB_PASSWORD",
        "REDIS_PASSWORD",
        "QDRANT_API_KEY",
    }
)


def _upper_digit_secret(length: int = 32) -> str:
    """Generate an uppercase letter and digit secret.

    Args:
        length: Secret length in characters.

    Returns:
        Random secret containing at least one uppercase letter and one digit.
    """
    if length < 2:
        raise ValueError("length must be at least 2")
    alphabet = string.ascii_uppercase + string.digits
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(ch.isalpha() for ch in value) and any(ch.isdigit() for ch in value):
            return value


def generate_jwt_secret(length: int = 32) -> str:
    """Generate a JWT secret matching the installer contract."""
    return _upper_digit_secret(length)


def generate_encryption_key(length: int = 32) -> str:
    """Generate a base64-encoded encryption key."""
    return base64.b64encode(secrets.token_bytes(length)).decode()


def generate_hmac_secret(length: int = 32) -> str:
    """Generate a hex-encoded HMAC secret.

    Args:
        length: Secret length in bytes. The default yields 64 hex characters.

    Returns:
        Hex-encoded secret.
    """
    return secrets.token_hex(length)


def generate_password(length: int = 32) -> str:
    """Generate an alphanumeric password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_api_key() -> str:
    """Generate a bootstrap API key with the commercial RC prefix."""
    return f"xagent-{secrets.token_urlsafe(32)}"


def generate_all_secrets(*, include_optional: bool = False) -> dict[str, str]:
    """Generate all installer-supported secrets.

    Args:
        include_optional: Include optional backing-service credentials.

    Returns:
        Dictionary keyed by unprefixed secret names.
    """
    generated = {
        "JWT_SECRET": generate_jwt_secret(64),
        "ENCRYPTION_KEY": generate_encryption_key(),
        "AUDIT_HMAC_SECRET": generate_hmac_secret(),
        "BOOTSTRAP_API_KEY": generate_api_key(),
        "S3_ACCESS_KEY": generate_password(24),
        "S3_SECRET_KEY": generate_password(48),
        "NEO4J_PASSWORD": generate_password(32),
    }
    if include_optional:
        generated.update(
            {
                "DB_PASSWORD": generate_password(32),
                "REDIS_PASSWORD": generate_password(32),
                "QDRANT_API_KEY": generate_password(32),
            }
        )
    return generated


def _env_key(name: str) -> str:
    if name in UNPREFIXED_ENV_KEYS:
        return name
    return name if name.startswith("XAGENT_") else f"XAGENT_{name}"


def format_env_output(secrets_dict: dict[str, str]) -> str:
    """Format secrets for an X-Agent .env file."""
    lines = [
        "# Generated X-Agent secrets.",
        "# Keep this file private and do not commit it to Git.",
        "",
    ]
    for key, value in secrets_dict.items():
        lines.append(f"{_env_key(key)}={value}")
    return "\n".join(lines) + "\n"


def format_json_output(secrets_dict: dict[str, str]) -> str:
    """Format secrets as JSON."""
    return json.dumps(secrets_dict, indent=2)


def save_to_file(content: str, filepath: Path) -> None:
    """Save generated output to a file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    _chmod_private(filepath)
    print(f"Secrets saved to: {filepath}", file=sys.stderr)


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        # Windows may not support POSIX chmod semantics for every filesystem.
        pass


def _parse_env_line(line: str) -> tuple[str, str] | None:
    match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
    if not match:
        return None
    key, raw_value = match.groups()
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def merge_env_values(existing: str, values: dict[str, str]) -> tuple[str, list[str], list[str]]:
    """Merge values into .env content without overwriting non-empty entries.

    Args:
        existing: Current .env text.
        values: Unprefixed or XAGENT-prefixed values to merge.

    Returns:
        Tuple of updated text, inserted keys, and preserved keys.
    """
    desired = {_env_key(key): value for key, value in values.items()}
    seen: set[str] = set()
    inserted: list[str] = []
    preserved: list[str] = []
    lines = existing.splitlines()
    updated_lines: list[str] = []

    for line in lines:
        parsed = _parse_env_line(line)
        if parsed is None:
            updated_lines.append(line)
            continue

        key, current_value = parsed
        if key not in desired:
            updated_lines.append(line)
            continue

        seen.add(key)
        if current_value:
            preserved.append(key)
            updated_lines.append(line)
            continue

        updated_lines.append(f"{key}={desired[key]}")
        inserted.append(key)

    for key, value in desired.items():
        if key in seen:
            continue
        if updated_lines and updated_lines[-1] != "":
            updated_lines.append("")
        updated_lines.append(f"{key}={value}")
        inserted.append(key)

    return "\n".join(updated_lines).rstrip() + "\n", inserted, preserved


def update_env_file(env_file: Path, secrets_dict: dict[str, str], *, create: bool = False) -> None:
    """Update an .env file with generated secrets.

    Existing non-empty values are preserved. Missing or blank generated keys are
    filled.

    Args:
        env_file: Path to the .env file.
        secrets_dict: Dictionary of unprefixed generated secrets.
        create: Create the file if it does not exist.
    """
    if env_file.exists():
        env_content = env_file.read_text(encoding="utf-8")
    elif create:
        env_content = ""
        env_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        print(f"File not found: {env_file}", file=sys.stderr)
        sys.exit(1)

    updated, inserted, preserved = merge_env_values(env_content, secrets_dict)
    env_file.write_text(updated, encoding="utf-8")
    _chmod_private(env_file)
    print(f"Updated {env_file}", file=sys.stderr)
    if inserted:
        print(f"Inserted: {', '.join(inserted)}", file=sys.stderr)
    if preserved:
        print(f"Preserved existing: {', '.join(preserved)}", file=sys.stderr)


def _validate_generated_shapes(secrets_dict: dict[str, str]) -> None:
    jwt = secrets_dict["JWT_SECRET"]
    encryption = secrets_dict["ENCRYPTION_KEY"]
    audit = secrets_dict["AUDIT_HMAC_SECRET"]
    bootstrap = secrets_dict["BOOTSTRAP_API_KEY"]

    upper_digit = re.compile(r"^[A-Z0-9]{64,}$")
    if not upper_digit.match(jwt):
        raise ValueError("JWT_SECRET must be at least 64 uppercase letters/digits")
    try:
        encryption_bytes = base64.b64decode(encryption, validate=True)
    except Exception as exc:
        raise ValueError("ENCRYPTION_KEY must be base64 for exactly 32 bytes") from exc
    if len(encryption_bytes) != 32:
        raise ValueError("ENCRYPTION_KEY must be base64 for exactly 32 bytes")
    if not re.fullmatch(r"[0-9a-f]{64}", audit):
        raise ValueError("AUDIT_HMAC_SECRET must be 64 lowercase hex characters")
    if not bootstrap.startswith("xagent-") or len(bootstrap) < 48:
        raise ValueError("BOOTSTRAP_API_KEY must use the xagent- prefix and be at least 48 characters")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate secure secrets for X-Agent configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate_secrets.py
  python scripts/generate_secrets.py --format json
  python scripts/generate_secrets.py --output secrets.txt
  python scripts/generate_secrets.py --env-file ~/.xagent/.env --create
        """,
    )
    parser.add_argument("--format", choices=["env", "json"], default="env")
    parser.add_argument("--output", type=Path, help="Output file path")
    parser.add_argument("--env-file", type=Path, help="Merge generated secrets into an .env file")
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create --env-file if it does not exist",
    )
    parser.add_argument(
        "--required-only",
        action="store_true",
        help="Only emit or merge JWT, encryption, audit HMAC, and bootstrap API key",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also emit optional DB, Redis, and Qdrant credentials",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate generated secret shapes and exit",
    )

    args = parser.parse_args()

    secrets_dict = generate_all_secrets(include_optional=args.include_optional)
    if args.required_only:
        secrets_dict = {key: secrets_dict[key] for key in REQUIRED_SECRET_KEYS}

    _validate_generated_shapes(secrets_dict)
    if args.check:
        print("Generated secret shapes are valid")
        return

    output = format_json_output(secrets_dict) if args.format == "json" else format_env_output(secrets_dict)

    if args.output:
        save_to_file(output, args.output)
    elif not args.env_file:
        print(output, end="")

    if args.env_file:
        update_env_file(args.env_file.expanduser(), secrets_dict, create=args.create)


if __name__ == "__main__":
    main()
