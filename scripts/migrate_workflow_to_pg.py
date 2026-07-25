#!/usr/bin/env python3
"""Migrate workflow data from JSON file storage to PostgreSQL.

Usage:
    python scripts/migrate_workflow_to_pg.py [--database-url URL] [--dry-run]

Reads:
  - data/workflows.json       (definitions)
  - data/workflow_runs.jsonl  (runs)
  - data/workflow_schedules.json (schedules)

Writes to the configured PostgreSQL database using SQLWorkflowRepository.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate workflow JSON data to PostgreSQL")
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL connection URL (default: from settings)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be migrated, don't write",
    )
    args = parser.parse_args()

    from backend.app.settings import get_settings

    settings = get_settings()
    database_url = args.database_url or settings.database_url

    if not database_url or "sqlite" in database_url:
        print("ERROR: A PostgreSQL database_url is required for migration.")
        print("  Use --database-url postgresql+asyncpg://user:pass@host:5432/db")
        sys.exit(1)

    from backend.app.core.workflow_store import (
        SQLWorkflowRepository,
        SQLWorkflowScheduleStore,
        create_workflow_engine,
    )
    from backend.app.core.workflows import (
        WorkflowDefinition,
        WorkflowRunRecord,
        WorkflowScheduleRecord,
    )

    engine = create_workflow_engine(database_url)
    repo = SQLWorkflowRepository(engine)
    schedule_store = SQLWorkflowScheduleStore(engine)

    # --- Definitions ---
    def_path = Path(settings.workflow_store_path)
    migrated_defs = 0
    if def_path.exists():
        definitions = json.loads(def_path.read_text(encoding="utf-8"))
        print(f"Found {len(definitions)} workflow definitions in {def_path}")
        for item in definitions:
            definition = WorkflowDefinition.model_validate(item)
            if args.dry_run:
                print(f"  [DRY-RUN] Would migrate definition: {definition.id} ({definition.name})")
            else:
                repo.upsert_definition(definition)
                print(f"  Migrated definition: {definition.id} ({definition.name})")
            migrated_defs += 1
    else:
        print(f"No definitions file at {def_path}")

    # --- Runs ---
    run_path = Path(settings.workflow_run_store_path)
    migrated_runs = 0
    if run_path.exists():
        lines = run_path.read_text(encoding="utf-8").strip().splitlines()
        print(f"Found {len(lines)} workflow runs in {run_path}")
        for line in lines:
            if not line.strip():
                continue
            run = WorkflowRunRecord.model_validate_json(line)
            if args.dry_run:
                print(f"  [DRY-RUN] Would migrate run: {run.run_id} (status={run.status.value})")
            else:
                repo.record_run(run)
                print(f"  Migrated run: {run.run_id} (status={run.status.value})")
            migrated_runs += 1
    else:
        print(f"No runs file at {run_path}")

    # --- Schedules ---
    sched_path = Path(settings.workflow_schedule_store_path)
    migrated_scheds = 0
    if sched_path.exists():
        schedules = json.loads(sched_path.read_text(encoding="utf-8"))
        print(f"Found {len(schedules)} workflow schedules in {sched_path}")
        for item in schedules:
            schedule = WorkflowScheduleRecord.model_validate(item)
            if args.dry_run:
                print(f"  [DRY-RUN] Would migrate schedule: {schedule.schedule_id}")
            else:
                schedule_store.upsert(schedule)
                print(f"  Migrated schedule: {schedule.schedule_id}")
            migrated_scheds += 1
    else:
        print(f"No schedules file at {sched_path}")

    print(f"\nMigration complete: {migrated_defs} definitions, {migrated_runs} runs, {migrated_scheds} schedules")
    if args.dry_run:
        print("(DRY-RUN mode: no data was written)")


if __name__ == "__main__":
    main()
