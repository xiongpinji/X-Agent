#!/usr/bin/env python3
"""Generate secure secrets for X-Agent configuration.

This script generates cryptographically secure random secrets for use in .env files.
Run this script and copy the output to your .env file.

Usage:
    python scripts/generate_secrets.py                    # Print to stdout
    python scripts/generate_secrets.py --format json      # JSON format
    python scripts/generate_secrets.py --output secrets.txt  # Save to file
    python scripts/generate_secrets.py --env-file .env.production  # Update .env file
"""

import argparse
import base64
import os
import re
import secrets
import string
import sys
from pathlib import Path


def generate_jwt_secret(length: int = 64) -> str:
    """Generate a secure JWT secret key.

    Args:
        length: Secret length in characters

    Returns:
        Secure random string
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_encryption_key(length: int = 32) -> str:
    """Generate a secure encryption key.

    Args:
        length: Key length in bytes

    Returns:
        Base64-encoded encryption key
    """
    key_bytes = os.urandom(length)
    return base64.b64encode(key_bytes).decode()


def generate_hmac_secret(length: int = 32) -> str:
    """Generate a secure HMAC secret.

    Args:
        length: Secret length in bytes

    Returns:
        Hex-encoded HMAC secret
    """
    return os.urandom(length).hex()


def generate_password(length: int = 32) -> str:
    """Generate a secure password.

    Args:
        length: Password length

    Returns:
        Secure random password
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_api_key(prefix: str = "sk") -> str:
    """Generate a secure API key.

    Args:
        prefix: API key prefix

    Returns:
        Secure API key
    """
    return f"{prefix}-{secrets.token_urlsafe(48)}"


def generate_all_secrets() -> dict:
    """Generate all required secrets.

    Returns:
        Dictionary of generated secrets
    """
    return {
        "JWT_SECRET": generate_jwt_secret(64),
        "ENCRYPTION_KEY": generate_encryption_key(32),
        "AUDIT_HMAC_SECRET": generate_hmac_secret(32),
        "BOOTSTRAP_API_KEY": generate_api_key("xagent"),
        "S3_ACCESS_KEY": generate_password(24),
        "S3_SECRET_KEY": generate_password(48),
        "NEO4J_PASSWORD": generate_password(32),
    }


def format_env_output(secrets_dict: dict) -> str:
    """Format secrets for .env file.

    Args:
        secrets_dict: Dictionary of secrets

    Returns:
        Formatted string for .env file
    """
    lines = [
        "# Generated secrets - Add these to your .env file",
        "# IMPORTANT: Keep these secrets secure and never commit them to Git!",
        "",
    ]

    for key, value in secrets_dict.items():
        lines.append(f"XAGENT_{key}={value}")

    return "\n".join(lines)


def format_json_output(secrets_dict: dict) -> str:
    """Format secrets as JSON.

    Args:
        secrets_dict: Dictionary of secrets

    Returns:
        JSON formatted string
    """
    import json
    return json.dumps(secrets_dict, indent=2)


def save_to_file(content: str, filepath: Path) -> None:
    """Save secrets to file.

    Args:
        content: Content to save
        filepath: File path

    Raises:
        IOError: If file cannot be written
    """
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
        filepath.chmod(0o600)  # Read/write for owner only
        print(f"Secrets saved to: {filepath}", file=sys.stderr)
    except IOError as e:
        print(f"Error saving secrets to file: {e}", file=sys.stderr)
        raise


def update_env_file(env_file: Path, secrets_dict: dict) -> None:
    """Update .env file with generated secrets.

    Args:
        env_file: Path to .env file
        secrets_dict: Dictionary of secrets

    Raises:
        FileNotFoundError: If .env file doesn't exist
    """
    if not env_file.exists():
        print(f"File not found: {env_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Updating {env_file}...", file=sys.stderr)
    env_content = env_file.read_text()

    # Update each secret
    for key, value in secrets_dict.items():
        env_key = f"XAGENT_{key}"
        # Replace or add the secret
        if env_key in env_content:
            # Replace existing value
            pattern = f"{env_key}=.*"
            env_content = re.sub(pattern, f"{env_key}={value}", env_content)
        else:
            # Add new value
            env_content += f"\n{env_key}={value}"

    env_file.write_text(env_content)
    env_file.chmod(0o600)
    print(f"Updated {env_file}", file=sys.stderr)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate secure secrets for X-Agent configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate_secrets.py
  python scripts/generate_secrets.py --format json
  python scripts/generate_secrets.py --output secrets.txt
  python scripts/generate_secrets.py --env-file .env.production
        """,
    )
    parser.add_argument(
        "--format",
        choices=["env", "json"],
        default="env",
        help="Output format (default: env)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (if not specified, prints to stdout)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Update .env file with generated secrets",
    )

    args = parser.parse_args()

    # Generate secrets
    print("Generating secure secrets...", file=sys.stderr)
    secrets_dict = generate_all_secrets()

    # Format output
    if args.format == "json":
        output = format_json_output(secrets_dict)
    else:
        output = format_env_output(secrets_dict)

    # Save or print
    if args.output:
        save_to_file(output, args.output)
    else:
        print(output)

    # Update .env file if specified
    if args.env_file:
        update_env_file(args.env_file, secrets_dict)

    print("", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("Secrets generated successfully!", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("", file=sys.stderr)
    print("IMPORTANT:", file=sys.stderr)
    print("1. Keep these secrets secure and never commit them to Git", file=sys.stderr)
    print("2. Store a backup in a secure password manager", file=sys.stderr)
    print("3. Rotate secrets regularly", file=sys.stderr)
    print("4. Never share these secrets with anyone", file=sys.stderr)
    print("", file=sys.stderr)


if __name__ == "__main__":
    main()
