#!/usr/bin/env python3
"""
X-Agent Local Endpoint Setup Script

Initializes local database, encryption, and configuration.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from backend.local import (
    LocalConfig,
    ConfigManager,
    DatabaseConfig,
    LocalDatabase,
    EncryptionManager,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def setup_directories(config: LocalConfig) -> None:
    """Create necessary directories.

    Args:
        config: Local configuration
    """
    db_dir = Path(config.db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created directory: {db_dir}")


def initialize_database(config: LocalConfig) -> LocalDatabase:
    """Initialize local database.

    Args:
        config: Local configuration

    Returns:
        LocalDatabase instance
    """
    logger.info("Initializing local database...")

    db_config = DatabaseConfig(
        db_path=config.db_path,
        timeout=config.db_timeout,
        enable_wal=config.db_enable_wal,
        enable_foreign_keys=config.db_enable_foreign_keys,
    )

    db = LocalDatabase(db_config)
    db.initialize()

    logger.info(f"Database initialized: {config.db_path}")
    return db


def initialize_encryption(config: LocalConfig) -> EncryptionManager:
    """Initialize encryption.

    Args:
        config: Local configuration

    Returns:
        EncryptionManager instance
    """
    logger.info("Initializing encryption...")

    encryption_manager = EncryptionManager()
    master_key = encryption_manager.generate_master_key()

    logger.info("Master key generated")
    logger.info(f"Encryption algorithm: {config.encryption_algorithm}")

    return encryption_manager


def save_configuration(config: LocalConfig, config_path: str | Path) -> None:
    """Save configuration to file.

    Args:
        config: Local configuration
        config_path: Path to save configuration
    """
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config.save_to_file(config_path)
    logger.info(f"Configuration saved: {config_path}")


def verify_setup(db: LocalDatabase) -> None:
    """Verify setup.

    Args:
        db: LocalDatabase instance
    """
    logger.info("Verifying setup...")

    # Check database
    stats = db.get_sync_stats()
    logger.info(f"Database stats: {stats}")

    # Check database size
    size_info = db.get_database_size()
    logger.info(f"Database size: {size_info['database_size_mb']} MB")

    logger.info("Setup verification completed successfully")


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(
        description="X-Agent Local Endpoint Setup"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="~/.xagent/config.json",
        help="Configuration file path",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="~/.xagent/local.db",
        help="Database file path",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset existing configuration",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing setup",
    )

    args = parser.parse_args()

    config_path = Path(args.config).expanduser()
    db_path = Path(args.db_path).expanduser()

    try:
        if args.verify_only:
            # Verify existing setup
            logger.info("Verifying existing setup...")
            if not config_path.exists():
                logger.error(f"Configuration file not found: {config_path}")
                sys.exit(1)

            config = LocalConfig.from_file(config_path)
            db = LocalDatabase(DatabaseConfig(db_path=config.db_path))
            verify_setup(db)

        else:
            # Full setup
            logger.info("Starting X-Agent Local Endpoint setup...")

            # Create configuration
            if config_path.exists() and not args.reset:
                logger.info(f"Loading existing configuration: {config_path}")
                config = LocalConfig.from_file(config_path)
            else:
                logger.info("Creating new configuration...")
                config = LocalConfig(db_path=str(db_path))

            # Setup directories
            setup_directories(config)

            # Initialize database
            db = initialize_database(config)

            # Initialize encryption
            encryption_manager = initialize_encryption(config)

            # Save configuration
            save_configuration(config, config_path)

            # Verify setup
            verify_setup(db)

            logger.info("Setup completed successfully!")
            logger.info(f"Configuration: {config_path}")
            logger.info(f"Database: {config.db_path}")

    except Exception as e:
        logger.error(f"Setup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
