"""Guard against a forked Alembic migration graph.

Background (2026-09-14): ``backend/migrations/alembic/versions/`` contained two
revisions that BOTH declared ``down_revision = None`` ("001_initial" and "001").
That produced two independent heads, so ``alembic upgrade head`` failed with
"Multiple head revisions are present" — the production Postgres path could not
be brought up at all. A merge revision (``4e125ce868ca``) joined the branches.

This test fails fast if the graph forks again. It reads the script directory
only and does NOT require a database.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _script_directory() -> ScriptDirectory:
    script_location = PROJECT_ROOT / "backend" / "migrations" / "alembic"
    assert script_location.is_dir(), f"missing migration dir: {script_location}"
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    # Use an absolute location so the test is independent of the current cwd.
    config.set_main_option("script_location", str(script_location))
    return ScriptDirectory.from_config(config)


def test_alembic_has_exactly_one_head() -> None:
    heads = _script_directory().get_heads()
    assert len(heads) == 1, (
        "Alembic migration graph must have exactly one head, but found "
        f"{heads}. Two revisions with down_revision=None fork the graph and "
        "break `alembic upgrade head`. Join them with a merge revision."
    )
