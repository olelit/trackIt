import sqlite3
from storage.schema import SCHEMA_VERSION, initialize_schema


def test_schema_version_is_int() -> None:
    assert isinstance(SCHEMA_VERSION, int)
    assert SCHEMA_VERSION >= 1


def test_initialize_schema_creates_tables() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t[0] for t in tables]
    assert "activity" in table_names
    assert "app_usage" in table_names


def test_initialize_schema_is_idempotent() -> None:
    """Calling initialize_schema twice must not raise errors."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)
    initialize_schema(conn)


def test_activity_table_columns() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)

    columns = conn.execute("PRAGMA table_info('activity')").fetchall()
    col_names = [c[1] for c in columns]
    assert "id" in col_names
    assert "name" in col_names
    assert "icon_path" in col_names
    assert "is_active" in col_names
    assert "total_duration_seconds" in col_names


def test_app_usage_table_columns() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)

    columns = conn.execute("PRAGMA table_info('app_usage')").fetchall()
    col_names = [c[1] for c in columns]
    assert "id" in col_names
    assert "activity_id" in col_names
    assert "app_name" in col_names
    assert "window_title" in col_names
    assert "duration_seconds" in col_names
    assert "last_seen_ts" in col_names


def test_foreign_key_cascade_delete() -> None:
    """Deleting an activity must cascade-delete its app_usage rows."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)

    conn.execute("INSERT INTO activity (name, is_active) VALUES ('Test', 1)")
    conn.execute("INSERT INTO app_usage (activity_id, app_name) VALUES (1, 'firefox')")
    conn.execute("INSERT INTO app_usage (activity_id, app_name) VALUES (1, 'konsole')")
    conn.commit()

    conn.execute("DELETE FROM activity WHERE id = 1")
    remaining = conn.execute("SELECT COUNT(*) FROM app_usage WHERE activity_id = 1").fetchone()[0]
    assert remaining == 0
