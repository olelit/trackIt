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


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [r[1] for r in rows]


def _get_column_type(conn: sqlite3.Connection, table_name: str, column_name: str) -> str | None:
    for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall():
        cid, name, ctype, notnull, dflt, pk = row
        if name == column_name:
            return (ctype or "").upper()
    return None


def _migrate_legacy_task_schema(conn: sqlite3.Connection) -> None:
    """Migrate a DB whose `task` table predates the current design.

    Legacy (from an earlier experiment outside this repo's history):
        task(id INTEGER PK, activity_id, task_key, task_name, source, last_seen_ts)
        app_usage.task_id INTEGER NOT NULL DEFAULT 0

    New (post-#2):
        task(id TEXT PK, title, first_seen_ts)
        app_usage.task_id TEXT NULL

    Idempotent: no-op if `task` is already on the new schema.
    """
    task_cols = _get_table_columns(conn, "task")
    if not task_cols:
        return

    # Detect legacy task table (has old task_key/task_name columns).
    if "task_key" not in task_cols and "task_name" not in task_cols:
        return

    logger.info("Migrating legacy task table")

    conn.execute("ALTER TABLE task RENAME TO task_legacy")
    conn.execute(CREATE_TASK_TABLE)
    conn.execute(
        """
        INSERT OR IGNORE INTO task (id, title, first_seen_ts)
        SELECT task_key, task_name, last_seen_ts
        FROM task_legacy
        WHERE task_key != ''
        """
    )

    # Migrate app_usage.task_id from INTEGER to TEXT (if still legacy).
    # Keep task_legacy around until app_usage is migrated so we can map
    # each legacy integer task_id to its (possibly non-existent) new id.
    app_cols = _get_table_columns(conn, "app_usage")
    if "task_id" in app_cols:
        task_id_type = _get_column_type(conn, "app_usage", "task_id")
        if task_id_type != "TEXT":
            logger.info("Migrating app_usage.task_id from %s to TEXT", task_id_type)
            conn.execute("ALTER TABLE app_usage RENAME TO app_usage_legacy")
            conn.execute(CREATE_APP_USAGE_TABLE)
            conn.execute(
                """
                INSERT INTO app_usage (
                    id, activity_id, app_name, window_title,
                    duration_seconds, last_seen_ts, task_id
                )
                SELECT
                    a.id, a.activity_id, a.app_name, a.window_title,
                    a.duration_seconds, a.last_seen_ts,
                    CASE
                        WHEN a.task_id = 0 THEN NULL
                        WHEN t.id IS NULL THEN NULL
                        ELSE t.id
                    END
                FROM app_usage_legacy a
                LEFT JOIN task_legacy tl ON tl.id = a.task_id
                LEFT JOIN task t ON t.id = tl.task_key
                """
            )
            conn.execute("DROP TABLE app_usage_legacy")
            conn.execute(CREATE_APP_USAGE_TASK_INDEX)

    conn.execute("DROP TABLE task_legacy")
    conn.commit()


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

    # Repair DBs created by a previous (pre-#2) design that have legacy columns
    # the CREATE-IF-NOT-E safety net cannot replace.
    _migrate_legacy_task_schema(conn)

    logger.info("Schema initialized (version %d)", SCHEMA_VERSION)
