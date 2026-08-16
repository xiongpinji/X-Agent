"""Fail-closed database migration and readiness gate."""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = PROJECT_ROOT / "backend" / "migrations" / "alembic.ini"
MIGRATIONS = PROJECT_ROOT / "backend" / "migrations"


def _config() -> Config:
    if not ALEMBIC_INI.is_file():
        raise FileNotFoundError(f"Alembic configuration is missing: {ALEMBIC_INI}")
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("prepend_sys_path", str(PROJECT_ROOT))
    return config


def _upgrade() -> None:
    if os.getenv("XAGENT_APP_MODE", "development").strip().lower() == "production":
        backup_id = os.getenv("XAGENT_PRE_MIGRATION_BACKUP_ID", "").strip()
        if not backup_id:
            raise RuntimeError(
                "XAGENT_PRE_MIGRATION_BACKUP_ID must reference a verified backup before production migration"
            )
    config = _config()
    command.upgrade(config, "head")
    command.current(config, check_heads=True)


def _check_current() -> None:
    command.current(_config(), check_heads=True)


def _retry(operation: Callable[[], None], *, timeout: float, interval: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            operation()
            return
        except Exception as error:  # database may still be starting
            last_error = error
            time.sleep(interval)
    error_type = type(last_error).__name__ if last_error is not None else "UnknownError"
    raise RuntimeError(f"database migration gate timed out ({error_type})") from last_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upgrade", "wait"))
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    if args.timeout <= 0 or args.interval <= 0:
        parser.error("--timeout and --interval must be positive")
    operation = _upgrade if args.action == "upgrade" else _check_current
    _retry(operation, timeout=args.timeout, interval=args.interval)


if __name__ == "__main__":
    main()
