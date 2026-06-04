import sqlite3

from storage.schema import SCHEMA_VERSION, initialize_schema


def test_schema_version_is_2() -> None:
    assert SCHEMA_VERSION == 2


def test_fresh_db_has_task_table() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t[0] for t in tables]
    assert "task" in table_names


def test_fresh_db_task_table_columns() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)

    columns = conn.execute("PRAGMA table_info('task')").fetchall()
    col_names = [c[1] for c in columns]
    assert "id" in col_names
    assert "title" in col_names
    assert "first_seen_ts" in col_names


def test_fresh_db_app_usage_has_task_id_column() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)

    columns = conn.execute("PRAGMA table_info('app_usage')").fetchall()
    col_names = [c[1] for c in columns]
    assert "task_id" in col_names


def test_fresh_db_has_app_usage_task_index() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)

    indexes = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_app_usage_activity_task'"
    ).fetchall()
    assert len(indexes) == 1


def test_initialize_schema_uses_user_version_2() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 2


def test_migrate_v1_to_v2_creates_task_and_column() -> None:
    """Simulate a v1 DB: pre-existing activity and app_usage tables, no task table."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    # Manually create the v1 schema
    conn.execute(
        """CREATE TABLE activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon_path TEXT,
            is_active INTEGER NOT NULL DEFAULT 0,
            total_duration_seconds INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE app_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL,
            app_name TEXT NOT NULL,
            window_title TEXT,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            last_seen_ts REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (activity_id) REFERENCES activity(id) ON DELETE CASCADE
        )"""
    )
    conn.execute("PRAGMA user_version = 1")
    conn.commit()

    # Insert a pre-existing row
    conn.execute("INSERT INTO activity (name, is_active) VALUES ('Work', 0)")
    conn.execute("INSERT INTO app_usage (activity_id, app_name) VALUES (1, 'firefox')")
    conn.commit()

    # Run the migration
    initialize_schema(conn)

    # Check the new state
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "task" in tables

    cols = [c[1] for c in conn.execute("PRAGMA table_info('app_usage')").fetchall()]
    assert "task_id" in cols

    # Existing row should still be there with task_id = NULL
    rows = conn.execute("SELECT activity_id, app_name, task_id FROM app_usage").fetchall()
    assert len(rows) == 1
    assert rows[0][2] is None


def test_initialize_schema_is_idempotent_v2() -> None:
    """Calling initialize_schema twice on a v2 DB must not raise."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)
    initialize_schema(conn)
