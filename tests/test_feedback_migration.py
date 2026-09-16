"""Guard: the Postgres schema must actually contain the feedback tables.

Background (2026-09-16)
-----------------------
``backend/app/models/feedback.py`` declared its own ``Base = declarative_base()``
while ``backend/migrations/alembic/env.py`` sets
``target_metadata = backend.app.models.Base.metadata`` — a *different* metadata
object.  Both exist, so ``alembic revision --autogenerate`` could never see
``FeedbackModel`` / ``FeedbackAnalysisModel``, and no revision ever created the
``feedback`` / ``feedback_analysis`` tables.  ``alembic upgrade head`` therefore
produced a Postgres schema that the production ``FeedbackStorePostgres`` path
could not use at all.

``tests/conftest.py`` called ``create_all`` on *both* metadata objects, which is
precisely why the gap survived: the test fixture papered over it.

This module pins three things:

1. the feedback models are registered on the canonical ``target_metadata``
   (so autogenerate stays truthful and the split cannot silently come back);
2. the new revision really builds a schema identical to the model — column
   names, nullability and index names are compared one by one;
3. the revision is reversible (``downgrade`` is not a stub).

Why the migration is executed on SQLite
---------------------------------------
The earlier revisions use ``postgresql.UUID`` / ``postgresql.ARRAY`` /
``postgresql.JSONB`` and ``CREATE EXTENSION pg_trgm``, so ``upgrade base:head``
cannot run on SQLite.  Stamping the database at the pre-revision first means
only the revision under test executes, and its DDL (String/Text/Float/JSON/
DateTime) is portable.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest
import sqlalchemy as sa

from backend.app.models import Base
from backend.app.models.feedback import FeedbackAnalysisModel, FeedbackModel

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "4e125ce868ca"
NEW_REVISION = "002_feedback_tables"
FEEDBACK_TABLES = ("feedback", "feedback_analysis")


def _url(db_path: pathlib.Path) -> str:
    """Sync SQLite URL.

    ``env.py`` takes its sync fallback branch for anything that is not
    asyncpg/aiosqlite/postgresql, which keeps the whole run out of an event
    loop (an async URL would call ``asyncio.run`` and collide with
    pytest-asyncio's loop).
    """
    return f"sqlite:///{db_path.as_posix()}"


def _run_alembic(db_path: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Drive the real CLI, the same way operators run it in production."""
    env = {**os.environ, "XAGENT_DATABASE_URL": _url(db_path)}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def _inspector(db_path: pathlib.Path) -> sa.Inspector:
    return sa.inspect(sa.create_engine(_url(db_path)))


@pytest.fixture(scope="module")
def migrated_db(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    db_path = tmp_path_factory.mktemp("feedback_migration") / "mig.db"

    stamp = _run_alembic(db_path, "stamp", PREVIOUS_REVISION)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"

    upgrade = _run_alembic(db_path, "upgrade", "head")
    assert upgrade.returncode == 0, f"upgrade failed:\n{upgrade.stdout}\n{upgrade.stderr}"

    return db_path


# --------------------------------------------------------------------------
# 1. Metadata registration — the root cause
# --------------------------------------------------------------------------
def test_feedback_models_register_on_canonical_metadata() -> None:
    """A separate Base is what hid these tables from autogenerate."""
    for model in (FeedbackModel, FeedbackAnalysisModel):
        assert model.__table__.metadata is Base.metadata, (
            f"{model.__name__} is bound to a non-canonical metadata object; "
            "alembic's target_metadata would not see it"
        )
    assert set(FEEDBACK_TABLES) <= set(Base.metadata.tables)


def test_new_revision_extends_the_merge_head() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location", str(PROJECT_ROOT / "backend" / "migrations" / "alembic")
    )
    script = ScriptDirectory.from_config(config)

    revision = script.get_revision(NEW_REVISION)
    assert revision is not None, f"{NEW_REVISION} is missing from the script directory"
    assert revision.down_revision == PREVIOUS_REVISION
    assert len(script.get_heads()) == 1


# --------------------------------------------------------------------------
# 2. The migration builds exactly what the model declares
# --------------------------------------------------------------------------
def test_migration_creates_both_tables(migrated_db: pathlib.Path) -> None:
    tables = set(_inspector(migrated_db).get_table_names())
    missing = set(FEEDBACK_TABLES) - tables
    assert not missing, f"migration did not create: {sorted(missing)}"


@pytest.mark.parametrize("model", [FeedbackModel, FeedbackAnalysisModel])
def test_migration_schema_matches_model(
    migrated_db: pathlib.Path, model: type[Base]
) -> None:
    table = model.__table__
    inspector = _inspector(migrated_db)

    reflected = {c["name"]: c["nullable"] for c in inspector.get_columns(table.name)}
    expected = {c.name: c.nullable for c in table.columns}
    assert reflected == expected, (
        f"{table.name}: only in DB={sorted(set(reflected) - set(expected))}, "
        f"only in model={sorted(set(expected) - set(reflected))}, "
        f"nullability drift={ {k: (reflected[k], expected[k]) for k in set(reflected) & set(expected) if reflected[k] != expected[k]} }"
    )

    db_indexes = {
        i["name"]
        for i in inspector.get_indexes(table.name)
        if not i["name"].startswith("sqlite_autoindex")
    }
    model_indexes = {i.name for i in table.indexes}
    assert db_indexes == model_indexes, (
        f"{table.name}: index drift={sorted(db_indexes ^ model_indexes)}"
    )


# --------------------------------------------------------------------------
# 3. Reversible
# --------------------------------------------------------------------------
def test_downgrade_drops_both_tables(tmp_path: pathlib.Path) -> None:
    db_path = tmp_path / "mig.db"

    assert _run_alembic(db_path, "stamp", PREVIOUS_REVISION).returncode == 0
    assert _run_alembic(db_path, "upgrade", NEW_REVISION).returncode == 0
    assert set(FEEDBACK_TABLES) <= set(_inspector(db_path).get_table_names())

    down = _run_alembic(db_path, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    remaining = set(_inspector(db_path).get_table_names())
    leftover = set(FEEDBACK_TABLES) & remaining
    assert not leftover, f"downgrade left tables behind: {sorted(leftover)}"
