"""Tests for migrating the legacy task schema (from a previous design) to the current one.

The legacy design (pre-#2) had a `task` table with columns:
- id INTEGER PK, activity_id, task_key, task_name, source, last_seen_ts

and `app_usage.task_id INTEGER NOT NULL DEFAULT 0`.

The current design (post-#2) has:
- task: id TEXT PK, title, first_seen_ts
- app_usage.task_id: TEXT NULL

If the user has an existing DB with the legacy schema, `initialize_schema` must migrate
the data so the new code's `t.title` query works.
"""

import sqlite3

from storage.schema import initialize_schema


def test_legacy_task_table_is_migrated_to_new_schema() -> None:
    """A DB with the legacy `task` table (with `task_key`/`task_name` columns) is
    migrated to the new schema on `initialize_schema`."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    # Manually create the LEGACY schema (different from current v1).
    conn.execute(
        """CREATE TABLE task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            task_key TEXT NOT NULL DEFAULT '',
            task_name TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            last_seen_ts REAL NOT NULL DEFAULT 0.0
        )"""
    )
    conn.execute("PRAGMA user_version = 2")  # already at v2 from a prior run
    conn.commit()

    # Insert a legacy task row (DRIVEO-4298)
    conn.execute(
        "INSERT INTO task (activity_id, task_key, task_name, source, last_seen_ts)"
        " VALUES (?, ?, ?, ?, ?)",
        (1, "DRIVEO-4298", "Rewrite something", "firefox", 100.0),
    )
    conn.commit()

    # Run the migration
    initialize_schema(conn)

    # The new task table must exist with the new columns
    cols = [c[1] for c in conn.execute("PRAGMA table_info('task')").fetchall()]
    assert "id" in cols
    assert "title" in cols
    assert "first_seen_ts" in cols
    assert "task_key" not in cols
    assert "task_name" not in cols

    # The legacy task row was migrated
    rows = conn.execute("SELECT id, title, first_seen_ts FROM task").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "DRIVEO-4298"
    assert rows[0][1] == "Rewrite something"
    assert rows[0][2] == 100.0


def test_legacy_task_with_empty_key_is_dropped() -> None:
    """Legacy rows with empty `task_key` represent the 'no task' group — drop them
    (the new code represents 'no task' as task_id IS NULL on app_usage)."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(
        """CREATE TABLE task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            task_key TEXT NOT NULL DEFAULT '',
            task_name TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            last_seen_ts REAL NOT NULL DEFAULT 0.0
        )"""
    )
    conn.execute("PRAGMA user_version = 2")
    conn.commit()

    # Two rows: one with a real key, one empty
    conn.execute(
        "INSERT INTO task (activity_id, task_key, task_name, source, last_seen_ts)"
        " VALUES (1, '', 'Без задачи', 'unknown', 50.0)"
    )
    conn.execute(
        "INSERT INTO task (activity_id, task_key, task_name, source, last_seen_ts)"
        " VALUES (1, 'DRIVE-1', 'Fix bug', 'firefox', 100.0)"
    )
    conn.commit()

    initialize_schema(conn)

    rows = conn.execute("SELECT id FROM task").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "DRIVE-1"


def test_legacy_migration_is_idempotent() -> None:
    """Running initialize_schema twice on a legacy DB must not error and must
    leave the new schema intact."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(
        """CREATE TABLE task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            task_key TEXT NOT NULL DEFAULT '',
            task_name TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            last_seen_ts REAL NOT NULL DEFAULT 0.0
        )"""
    )
    conn.execute("PRAGMA user_version = 2")
    conn.execute(
        "INSERT INTO task (activity_id, task_key, task_name, source, last_seen_ts)"
        " VALUES (1, 'DRIVE-1', 'Fix bug', 'firefox', 100.0)"
    )
    conn.commit()

    initialize_schema(conn)
    initialize_schema(conn)  # second call must be a no-op

    cols = [c[1] for c in conn.execute("PRAGMA table_info('task')").fetchall()]
    assert "title" in cols
    assert "task_key" not in cols
    rows = conn.execute("SELECT id, title FROM task").fetchall()
    assert rows == [("DRIVE-1", "Fix bug")]


def test_legacy_migration_drops_orphan_task_id_references() -> None:
    """app_usage rows pointing to a legacy task that gets dropped (e.g. the empty
    'no task' placeholder) must end up with task_id=NULL, not a dangling FK."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(
        """CREATE TABLE task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            task_key TEXT NOT NULL DEFAULT '',
            task_name TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            last_seen_ts REAL NOT NULL DEFAULT 0.0
        )"""
    )
    conn.execute("PRAGMA user_version = 2")
    conn.execute(
        "INSERT INTO task (activity_id, task_key, task_name, source, last_seen_ts)"
        " VALUES (1, '', 'No task', 'unknown', 50.0)"
    )
    conn.execute(
        "INSERT INTO task (activity_id, task_key, task_name, source, last_seen_ts)"
        " VALUES (1, 'DRIVE-1', 'Fix bug', 'firefox', 100.0)"
    )

    # app_usage with legacy integer task_id: 1 = the orphan, 2 = the real one
    conn.execute(
        """CREATE TABLE app_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            app_name TEXT NOT NULL,
            window_title TEXT,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            last_seen_ts REAL NOT NULL DEFAULT 0.0,
            task_id INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon_path TEXT,
            is_active INTEGER NOT NULL DEFAULT 0,
            total_duration_seconds INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute("INSERT INTO activity (id, name) VALUES (1, 'A')")
    conn.execute(
        "INSERT INTO app_usage (activity_id, app_name, task_id) VALUES (1, 'foo', 1)"
    )
    conn.execute(
        "INSERT INTO app_usage (activity_id, app_name, task_id) VALUES (1, 'bar', 2)"
    )
    conn.execute(
        "INSERT INTO app_usage (activity_id, app_name, task_id) VALUES (1, 'baz', 0)"
    )
    conn.commit()

    initialize_schema(conn)

    # All 3 rows preserved
    assert len(conn.execute("SELECT * FROM app_usage").fetchall()) == 3
    # task_id=1 (orphan) and task_id=0 -> NULL
    # task_id=2 (legacy id of DRIVE-1) -> "DRIVE-1"
    rows = conn.execute(
        "SELECT app_name, task_id FROM app_usage ORDER BY app_name"
    ).fetchall()
    by_name = {r[0]: r[1] for r in rows}
    assert by_name == {"bar": "DRIVE-1", "baz": None, "foo": None}


def test_legacy_migration_preserves_user_version() -> None:
    """After legacy migration, user_version remains 2 (we're now on the new v2)."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """CREATE TABLE task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            task_key TEXT NOT NULL DEFAULT '',
            task_name TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            last_seen_ts REAL NOT NULL DEFAULT 0.0
        )"""
    )
    conn.execute("PRAGMA user_version = 2")
    conn.commit()

    initialize_schema(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
