import sqlite3
import logging

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

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
    FOREIGN KEY (activity_id) REFERENCES activity(id) ON DELETE CASCADE
);
"""


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_ACTIVITY_TABLE)
    conn.execute(CREATE_APP_USAGE_TABLE)
    conn.commit()
    logger.info("Schema initialized (version %d)", SCHEMA_VERSION)
