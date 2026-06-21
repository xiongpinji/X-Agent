#!/usr/bin/env python3
"""Backup and recovery management for X-Agent production environment."""

import os
import sys
import json
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

HTTP_TIMEOUT_SECONDS = 30


class BackupManager:
    """Manages backups for all X-Agent data stores."""

    def __init__(self, backup_dir: str = "./backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def backup_postgresql(self, db_host: str, db_user: str, db_password: str, db_name: str) -> str:
        """Backup PostgreSQL database."""
        logger.info(f"Starting PostgreSQL backup for {db_name}...")

        backup_file = self.backup_dir / f"postgres_{db_name}_{self.timestamp}.sql.gz"

        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password

            cmd = [
                'pg_dump',
                '-h', db_host,
                '-U', db_user,
                '-d', db_name,
                '--verbose',
                '--no-password'
            ]

            with open(backup_file, 'wb') as f:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env
                )
                import gzip
                with gzip.open(f, 'wb') as gz:
                    for chunk in iter(lambda: process.stdout.read(4096), b''):
                        gz.write(chunk)

            if process.wait() == 0:
                logger.info(f"PostgreSQL backup completed: {backup_file}")
                return str(backup_file)
            else:
                logger.error(f"PostgreSQL backup failed: {process.stderr.read().decode()}")
                raise Exception("PostgreSQL backup failed")

        except Exception as e:
            logger.error(f"PostgreSQL backup error: {str(e)}")
            raise

    def backup_qdrant(self, qdrant_url: str) -> str:
        """Backup Qdrant vector database."""
        logger.info(f"Starting Qdrant backup from {qdrant_url}...")

        backup_file = self.backup_dir / f"qdrant_{self.timestamp}.snapshot"

        try:
            import requests

            # Create snapshot
            response = requests.post(f"{qdrant_url}/snapshots", timeout=HTTP_TIMEOUT_SECONDS)
            if response.status_code != 200:
                raise Exception(f"Failed to create snapshot: {response.text}")

            snapshot_name = response.json()['snapshot_name']
            logger.info(f"Snapshot created: {snapshot_name}")

            # Download snapshot
            response = requests.get(
                f"{qdrant_url}/snapshots/{snapshot_name}",
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                raise Exception(f"Failed to download snapshot: {response.text}")

            with open(backup_file, 'wb') as f:
                f.write(response.content)

            logger.info(f"Qdrant backup completed: {backup_file}")
            return str(backup_file)

        except Exception as e:
            logger.error(f"Qdrant backup error: {str(e)}")
            raise

    def backup_redis(self, redis_host: str, redis_port: int = 6379) -> str:
        """Backup Redis database."""
        logger.info(f"Starting Redis backup from {redis_host}:{redis_port}...")

        backup_file = self.backup_dir / f"redis_{self.timestamp}.rdb"

        try:
            import redis

            r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
            r.bgsave()

            # Wait for backup to complete
            import time
            for _ in range(60):
                if r.lastsave() > datetime.now().timestamp() - 5:
                    break
                time.sleep(1)

            # Copy RDB file
            rdb_path = Path(f"/var/lib/redis/dump.rdb")
            if rdb_path.exists():
                import shutil
                shutil.copy(rdb_path, backup_file)
                logger.info(f"Redis backup completed: {backup_file}")
                return str(backup_file)
            else:
                logger.warning("Redis RDB file not found at default location")
                return ""

        except Exception as e:
            logger.error(f"Redis backup error: {str(e)}")
            raise

    def backup_neo4j(self, neo4j_host: str, neo4j_user: str, neo4j_password: str) -> str:
        """Backup Neo4j graph database."""
        logger.info(f"Starting Neo4j backup from {neo4j_host}...")

        backup_file = self.backup_dir / f"neo4j_{self.timestamp}.dump"

        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                f"bolt://{neo4j_host}:7687",
                auth=(neo4j_user, neo4j_password)
            )

            with driver.session() as session:
                # Export all data
                result = session.run("CALL apoc.export.json.all($file, {})", file=str(backup_file))
                logger.info(f"Neo4j backup completed: {backup_file}")

            driver.close()
            return str(backup_file)

        except Exception as e:
            logger.error(f"Neo4j backup error: {str(e)}")
            raise

    def backup_configs(self) -> str:
        """Backup configuration files."""
        logger.info("Starting configuration backup...")

        backup_file = self.backup_dir / f"configs_{self.timestamp}.tar.gz"

        try:
            import tarfile

            config_dirs = [
                ".env",
                "config/",
                "monitoring/",
                "docker-compose.yml"
            ]

            with tarfile.open(backup_file, "w:gz") as tar:
                for item in config_dirs:
                    if Path(item).exists():
                        tar.add(item, arcname=item)

            logger.info(f"Configuration backup completed: {backup_file}")
            return str(backup_file)

        except Exception as e:
            logger.error(f"Configuration backup error: {str(e)}")
            raise

    def verify_backup(self, backup_file: str) -> bool:
        """Verify backup integrity."""
        logger.info(f"Verifying backup: {backup_file}")

        try:
            path = Path(backup_file)
            if not path.exists():
                logger.error(f"Backup file not found: {backup_file}")
                return False

            if path.stat().st_size == 0:
                logger.error(f"Backup file is empty: {backup_file}")
                return False

            logger.info(f"Backup verification passed: {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Backup verification error: {str(e)}")
            return False

    def cleanup_old_backups(self, retention_days: int = 30) -> None:
        """Remove backups older than retention period."""
        logger.info(f"Cleaning up backups older than {retention_days} days...")

        cutoff_date = datetime.now() - timedelta(days=retention_days)

        try:
            for backup_file in self.backup_dir.glob("*"):
                if backup_file.is_file():
                    mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        backup_file.unlink()
                        logger.info(f"Deleted old backup: {backup_file}")

        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

    def create_full_backup(self, config: Dict) -> Dict[str, str]:
        """Create full backup of all systems."""
        logger.info("Starting full system backup...")

        backups = {}

        try:
            # PostgreSQL
            if config.get('postgresql', {}).get('enabled'):
                backups['postgresql'] = self.backup_postgresql(
                    config['postgresql']['host'],
                    config['postgresql']['user'],
                    config['postgresql']['password'],
                    config['postgresql']['database']
                )

            # Qdrant
            if config.get('qdrant', {}).get('enabled'):
                backups['qdrant'] = self.backup_qdrant(config['qdrant']['url'])

            # Redis
            if config.get('redis', {}).get('enabled'):
                backups['redis'] = self.backup_redis(
                    config['redis']['host'],
                    config['redis']['port']
                )

            # Neo4j
            if config.get('neo4j', {}).get('enabled'):
                backups['neo4j'] = self.backup_neo4j(
                    config['neo4j']['host'],
                    config['neo4j']['user'],
                    config['neo4j']['password']
                )

            # Configs
            backups['configs'] = self.backup_configs()

            # Cleanup old backups
            self.cleanup_old_backups()

            logger.info("Full system backup completed successfully")
            return backups

        except Exception as e:
            logger.error(f"Full backup error: {str(e)}")
            raise


class RecoveryManager:
    """Manages recovery from backups."""

    @staticmethod
    def restore_postgresql(backup_file: str, db_host: str, db_user: str, db_password: str, db_name: str) -> bool:
        """Restore PostgreSQL database from backup."""
        logger.info(f"Starting PostgreSQL restore from {backup_file}...")

        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password

            import gzip
            with gzip.open(backup_file, 'rb') as f:
                cmd = [
                    'psql',
                    '-h', db_host,
                    '-U', db_user,
                    '-d', db_name,
                    '--no-password'
                ]

                process = subprocess.Popen(
                    cmd,
                    stdin=f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env
                )

                if process.wait() == 0:
                    logger.info("PostgreSQL restore completed successfully")
                    return True
                else:
                    logger.error(f"PostgreSQL restore failed: {process.stderr.read().decode()}")
                    return False

        except Exception as e:
            logger.error(f"PostgreSQL restore error: {str(e)}")
            return False

    @staticmethod
    def restore_qdrant(backup_file: str, qdrant_url: str) -> bool:
        """Restore Qdrant from backup."""
        logger.info(f"Starting Qdrant restore from {backup_file}...")

        try:
            import requests

            with open(backup_file, 'rb') as f:
                files = {'snapshot': f}
                response = requests.post(
                    f"{qdrant_url}/snapshots/recover",
                    files=files,
                    timeout=HTTP_TIMEOUT_SECONDS,
                )

            if response.status_code == 200:
                logger.info("Qdrant restore completed successfully")
                return True
            else:
                logger.error(f"Qdrant restore failed: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Qdrant restore error: {str(e)}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='X-Agent Backup & Recovery Manager')
    parser.add_argument('action', choices=['backup', 'restore', 'verify', 'cleanup'],
                        help='Action to perform')
    parser.add_argument('--config', default='backup_config.json',
                        help='Backup configuration file')
    parser.add_argument('--backup-file', help='Backup file for restore/verify')
    parser.add_argument('--retention-days', type=int, default=30,
                        help='Retention period for backups in days')

    args = parser.parse_args()

    # Load configuration
    if not Path(args.config).exists():
        logger.error(f"Configuration file not found: {args.config}")
        sys.exit(1)

    with open(args.config) as f:
        config = json.load(f)

    if args.action == 'backup':
        manager = BackupManager()
        backups = manager.create_full_backup(config)
        logger.info(f"Backups created: {json.dumps(backups, indent=2)}")

    elif args.action == 'restore':
        if not args.backup_file:
            logger.error("--backup-file required for restore action")
            sys.exit(1)
        recovery = RecoveryManager()
        # Implement restore logic based on backup file type

    elif args.action == 'verify':
        if not args.backup_file:
            logger.error("--backup-file required for verify action")
            sys.exit(1)
        manager = BackupManager()
        if manager.verify_backup(args.backup_file):
            sys.exit(0)
        else:
            sys.exit(1)

    elif args.action == 'cleanup':
        manager = BackupManager()
        manager.cleanup_old_backups(args.retention_days)


if __name__ == '__main__':
    main()
