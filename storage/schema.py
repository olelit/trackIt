import logging
import sqlite3

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

CREATE_ACTIVITY_TABLE = """
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    icon_path TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    total_duration_seconds INTEGER NOT NULL DEFAULT 0
);
"""

CREATE_APP_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS app_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    app_name TEXT NOT NULL,
    window_title TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    last_seen_ts REAL NOT NULL DEFAULT 0.0,
    task_id TEXT,
    FOREIGN KEY (activity_id) REFERENCES activity(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE SET NULL
);
"""

CREATE_TASK_TABLE = """
CREATE TABLE IF NOT EXISTS task (
    id TEXT PRIMARY KEY,
    title TEXT,
    first_seen_ts REAL NOT NULL
);
"""

CREATE_APP_USAGE_TASK_INDEX = """
CREATE INDEX IF NOT EXISTS idx_app_usage_activity_task
    ON app_usage(activity_id, task_id);
"""


def _get_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def _set_user_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()


def migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Bring a v1 DB up to v2: add task table and app_usage.task_id column.

    Idempotent only at the `user_version` gate; the ALTER TABLE is not.
    """
    conn.execute(CREATE_TASK_TABLE)
    conn.execute(
        "ALTER TABLE app_usage ADD COLUMN task_id TEXT REFERENCES task(id) ON DELETE SET NULL"
    )
    conn.execute(CREATE_APP_USAGE_TASK_INDEX)
    _set_user_version(conn, 2)
    conn.commit()
    logger.info("Migrated schema v1 -> v2")


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema initializer. Applies missing migrations, then runs the v2 schema as a safety net."""
    version = _get_user_version(conn)
    if version < 1:
        conn.execute(CREATE_ACTIVITY_TABLE)
        conn.execute(CREATE_APP_USAGE_TABLE)
        conn.execute(CREATE_TASK_TABLE)
        conn.execute(CREATE_APP_USAGE_TASK_INDEX)
        _set_user_version(conn, 2)
        conn.commit()
    elif version < 2:
        migrate_v1_to_v2(conn)

    # Safety net (idempotent CREATE IF NOT EXISTS)
    conn.execute(CREATE_ACTIVITY_TABLE)
    conn.execute(CREATE_APP_USAGE_TABLE)
    conn.execute(CREATE_TASK_TABLE)
    conn.execute(CREATE_APP_USAGE_TASK_INDEX)
    conn.commit()
    logger.info("Schema initialized (version %d)", SCHEMA_VERSION)
