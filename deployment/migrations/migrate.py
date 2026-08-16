#!/usr/bin/env python3
"""Retired legacy deployment mutation entrypoint.

Production schema changes are performed by ``backend.app.ops.migration_gate``
and database recovery is performed by the explicitly confirmed
``deployment/scripts/restore-database.sh``. Keeping the old rollback and
automatic-restore implementation callable would bypass those safety gates.
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    """Reject every legacy mutation before reading configuration or paths."""
    logger.error(
        "Legacy mutating command is disabled. Use backend.app.ops.migration_gate "
        "for schema upgrades, deployment/scripts/backup-database.sh for backups, "
        "and deployment/scripts/restore-database.sh for approved recovery."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
