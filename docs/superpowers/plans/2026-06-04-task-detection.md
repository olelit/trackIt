# Task Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect task IDs (e.g. `DRIVE-1234`) in active window titles and group per-app time tracking by task in the right pane.

**Architecture:** A new `TaskDetector` (pure functions) parses window titles into a `TaskKey` (id + title). A `ConfigService` loads the user's regex from `trackit.json` (auto-created with the YouTrack/Jira default if missing). `TimeTrackingService` flushes segments on task change, just like it does on window change. The right pane is reshaped from a `QListWidget` to a `QTreeWidget` with two top-level groups ("Tasks" + "No task"). A new `task` table stores first-seen titles, joined to `app_usage` via a `task_id` foreign key.

**Tech Stack:** Python 3.13, PySide6 (Qt6), SQLite, pytest, ruff, mypy strict.

---

## File Structure

**New files:**
- `models/task_key.py` — `TaskKey` frozen dataclass (id, title).
- `models/task.py` — `Task` and `TaskGroup` frozen dataclasses.
- `services/task_detector.py` — `TaskDetector` class, `DEFAULT_TASK_ID_REGEX` constant.
- `services/config_service.py` — `ConfigService` class, `DEFAULT_CONFIG`, `CONFIG_FILENAME`, `find_project_root()`.
- `tests/test_task_detector.py`
- `tests/test_config_service.py`
- `tests/test_task_models.py`
- `tests/test_repository_task.py` (extends `test_repository.py` patterns)
- `tests/test_schema_task.py` (extends `test_schema.py` patterns)
- `tests/test_time_tracking_task.py`
- `tests/test_ui_activity_detail_tasks.py`

**Modified files:**
- `models/app_usage.py` — add `task_id: str | None = None` field.
- `storage/schema.py` — add `CREATE_TASK_TABLE`, `CREATE_APP_USAGE_TASK_INDEX`, schema-version dispatcher (`migrate_v1_to_v2`).
- `storage/repository.py` — add `TaskRepository`, extend `AppUsageRepository` with `task_id` param on `add_duration`/`upsert`, add `get_grouped_by_task`.
- `services/storage_service.py` — expose `self.tasks: TaskRepository`.
- `services/time_tracking.py` — accept `detector: TaskDetector`, add `_current_task`, flush on task change, add `current_task_id` property.
- `ui/activity_detail.py` — replace `QListWidget` with `QTreeWidget` rendering "Tasks" + "No task" groups.
- `core/app.py` — instantiate `ConfigService`, thread `detector` through `create_services`.
- `tests/test_app.py` — `create_services` signature change.
- `tests/test_schema.py` — extend with v2 migration tests.
- `tests/test_time_tracking.py` — keep existing tests working after signature change.
- `tests/test_ui_activity_detail.py` — update for tree widget API.

---

## Task 1: TaskKey dataclass

**Files:**
- Create: `models/task_key.py`
- Test: `tests/test_task_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_task_models.py`:

```python
from models.task import Task, TaskGroup
from models.task_key import TaskKey


def test_task_key_default_is_no_task() -> None:
    k = TaskKey()
    assert k.task_id is None
    assert k.task_title is None


def test_task_key_with_id_only() -> None:
    k = TaskKey(task_id="DRIVE-1234")
    assert k.task_id == "DRIVE-1234"
    assert k.task_title is None


def test_task_key_with_id_and_title() -> None:
    k = TaskKey(task_id="DRIVE-1234", task_title="Fix bug")
    assert k.task_id == "DRIVE-1234"
    assert k.task_title == "Fix bug"


def test_task_key_is_frozen() -> None:
    k = TaskKey(task_id="X")
    try:
        k.task_id = "Y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("TaskKey should be frozen")


def test_task_key_equality() -> None:
    a = TaskKey(task_id="X", task_title="title")
    b = TaskKey(task_id="X", task_title="title")
    assert a == b


def test_task_key_inequality_on_id() -> None:
    a = TaskKey(task_id="X")
    b = TaskKey(task_id="Y")
    assert a != b


def test_task_key_is_hashable() -> None:
    a = TaskKey(task_id="X", task_title="t")
    b = TaskKey(task_id="X", task_title="t")
    assert {a, b} == {a}


def test_task_dataclass_defaults() -> None:
    t = Task(id="DRIVE-1234")
    assert t.id == "DRIVE-1234"
    assert t.title is None
    assert t.first_seen_ts == 0.0


def test_task_group_holds_apps() -> None:
    g = TaskGroup(task_id="X", task_title="t", apps=())
    assert g.task_id == "X"
    assert g.apps == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_task_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models.task_key'`

- [ ] **Step 3: Write the model**

Create `models/task_key.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskKey:
    task_id: str | None = None
    task_title: str | None = None
```

- [ ] **Step 4: Create the second model**

Create `models/task.py`:

```python
from dataclasses import dataclass

from models.app_usage import AppUsage


@dataclass(frozen=True)
class Task:
    id: str
    title: str | None = None
    first_seen_ts: float = 0.0


@dataclass(frozen=True)
class TaskGroup:
    task_id: str | None
    task_title: str | None
    apps: tuple[AppUsage, ...] = ()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_task_models.py -v`
Expected: 9 passed

- [ ] **Step 6: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check models/task_key.py models/task.py tests/test_task_models.py
MYPYPATH=. .venv/bin/mypy models/task_key.py models/task.py
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add models/task_key.py models/task.py tests/test_task_models.py
git commit -m "feat: add TaskKey, Task, and TaskGroup dataclasses"
```

---

## Task 2: TaskDetector

**Files:**
- Create: `services/task_detector.py`
- Test: `tests/test_task_detector.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_task_detector.py`:

```python
import re

import pytest

from models.task_key import TaskKey
from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector


@pytest.fixture
def detector() -> TaskDetector:
    return TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))


def test_default_regex_is_string() -> None:
    assert isinstance(DEFAULT_TASK_ID_REGEX, str)
    assert DEFAULT_TASK_ID_REGEX


def test_detect_none_title(detector: TaskDetector) -> None:
    assert detector.detect(None) == TaskKey(None, None)


def test_detect_empty_title(detector: TaskDetector) -> None:
    assert detector.detect("") == TaskKey(None, None)


def test_detect_no_match(detector: TaskDetector) -> None:
    assert detector.detect("Just a normal page title") == TaskKey(None, None)


def test_detect_simple_match(detector: TaskDetector) -> None:
    result = detector.detect("DRIVE-1234")
    assert result == TaskKey(task_id="DRIVE-1234", task_title=None)


def test_detect_title_with_id_suffix(detector: TaskDetector) -> None:
    """The canonical example: 'Rewrite-... : DRIVEO-4298'."""
    result = detector.detect("Rewrite-update-price-logic-to-websockets-and-jobs : DRIVEO-4298")
    assert result == TaskKey(
        task_id="DRIVEO-4298",
        task_title="Rewrite-update-price-logic-to-websockets-and-jobs",
    )


def test_detect_title_with_id_prefix(detector: TaskDetector) -> None:
    result = detector.detect("DRIVE-1234: fix login bug")
    assert result.task_id == "DRIVE-1234"
    assert result.task_title == "fix login bug"


def test_detect_multiple_matches_first_wins(detector: TaskDetector) -> None:
    result = detector.detect("DRIVE-1234 is related to DRIVE-5678")
    assert result.task_id == "DRIVE-1234"


def test_detect_strips_trailing_colon_and_space() -> None:
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    result = detector.detect("My title : DRIVE-1234")
    assert result.task_title == "My title"


def test_detect_strips_trailing_dash() -> None:
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    result = detector.detect("My title - DRIVE-1234")
    assert result.task_title == "My title"


def test_detect_keeps_id_when_no_prefix(detector: TaskDetector) -> None:
    result = detector.detect("DRIVE-1234")
    assert result.task_id == "DRIVE-1234"
    assert result.task_title is None


def test_detect_title_only_whitespace_prefix_returns_none_title() -> None:
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    result = detector.detect("  : DRIVE-1234")
    assert result.task_id == "DRIVE-1234"
    assert result.task_title is None


def test_detect_lowercase_id_does_not_match() -> None:
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    result = detector.detect("drive-1234 lowercase")
    assert result == TaskKey(None, None)


def test_custom_regex() -> None:
    """A custom regex (e.g. for GitLab-style) should work too."""
    detector = TaskDetector(re.compile(r"#(\d+)"))
    result = detector.detect("Some title #42 extra")
    assert result.task_id == "#42"
    assert result.task_title == "Some title"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_task_detector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.task_detector'`

- [ ] **Step 3: Write the implementation**

Create `services/task_detector.py`:

```python
import logging
import re

from models.task_key import TaskKey

logger = logging.getLogger(__name__)

DEFAULT_TASK_ID_REGEX = r"\b([A-Z][A-Z0-9]+-\d+)\b"

_STRIP_CHARS = ": \t-"


class TaskDetector:
    """Extracts a task ID and descriptive title from a window title.

    The detector is stateless and side-effect-free. Construct one per app
    session via ConfigService and share it across services.
    """

    def __init__(self, regex: re.Pattern[str]) -> None:
        self._regex = regex

    def detect(self, window_title: str | None) -> TaskKey:
        if not window_title:
            return TaskKey(None, None)

        match = self._regex.search(window_title)
        if match is None:
            return TaskKey(None, None)

        task_id = match.group(1)
        prefix = window_title[: match.start()].rstrip(_STRIP_CHARS)
        task_title = prefix or None
        return TaskKey(task_id, task_title)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_task_detector.py -v`
Expected: 15 passed

- [ ] **Step 5: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check services/task_detector.py tests/test_task_detector.py
MYPYPATH=. .venv/bin/mypy services/task_detector.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add services/task_detector.py tests/test_task_detector.py
git commit -m "feat: add TaskDetector with configurable regex"
```

---

## Task 3: Schema migration (v1 → v2)

**Files:**
- Modify: `storage/schema.py`
- Test: `tests/test_schema_task.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_schema_task.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_schema_task.py -v`
Expected: FAIL on `test_schema_version_is_2` (still 1) and `test_fresh_db_has_task_table` (no task table).

- [ ] **Step 3: Update `storage/schema.py`**

Replace the entire contents of `storage/schema.py` with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_schema_task.py -v`
Expected: 8 passed

- [ ] **Step 5: Verify the existing test_schema.py still passes**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_schema.py -v`
Expected: 5 passed. (`test_schema_version_is_int` checks `>= 1` — still true. `test_initialize_schema_creates_tables` still passes; the safety-net `CREATE IF NOT EXISTS` for `activity` and `app_usage` keeps them. `test_activity_table_columns` and `test_app_usage_table_columns` still pass; we kept the existing columns and only added `task_id` to `app_usage`.)

- [ ] **Step 6: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check storage/schema.py tests/test_schema_task.py
MYPYPATH=. .venv/bin/mypy storage/schema.py
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add storage/schema.py tests/test_schema_task.py
git commit -m "feat: schema v2 with task table and app_usage.task_id"
```

---

## Task 4: AppUsage gains task_id

**Files:**
- Modify: `models/app_usage.py`
- Test: extend `tests/test_models.py` (or new file)

- [ ] **Step 1: Add the field**

Read `models/app_usage.py` and replace it with:

```python
from dataclasses import dataclass


@dataclass
class AppUsage:
    id: int = 0
    activity_id: int = 0
    app_name: str = ""
    window_title: str | None = None
    duration_seconds: int = 0
    last_seen_ts: float = 0.0
    task_id: str | None = None
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -q 2>&1 | tail -2`
Expected: 98 passed (no regressions; new field has a default of `None`).

- [ ] **Step 3: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check models/app_usage.py
MYPYPATH=. .venv/bin/mypy models/app_usage.py
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add models/app_usage.py
git commit -m "feat: AppUsage gains task_id field"
```

---

## Task 5: TaskRepository + AppUsageRepository task_id support

**Files:**
- Modify: `storage/repository.py`
- Test: `tests/test_repository_task.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_repository_task.py`:

```python
import sqlite3

import pytest

from models.app_usage import AppUsage
from storage.repository import AppUsageRepository, TaskRepository
from storage.schema import initialize_schema


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    initialize_schema(c)
    return c


class TestTaskRepository:
    def test_upsert_inserts_new_task(self, conn: sqlite3.Connection) -> None:
        repo = TaskRepository(conn)
        repo.upsert(id="DRIVE-1234", title="Fix bug", first_seen_ts=100.0)
        task = repo.get("DRIVE-1234")
        assert task is not None
        assert task.id == "DRIVE-1234"
        assert task.title == "Fix bug"
        assert task.first_seen_ts == 100.0

    def test_upsert_does_not_overwrite_existing_title(self, conn: sqlite3.Connection) -> None:
        """First-seen title wins. Later upserts with a different title are ignored."""
        repo = TaskRepository(conn)
        repo.upsert(id="DRIVE-1234", title="Original title", first_seen_ts=100.0)
        repo.upsert(id="DRIVE-1234", title="Different title", first_seen_ts=200.0)
        task = repo.get("DRIVE-1234")
        assert task is not None
        assert task.title == "Original title"

    def test_upsert_with_none_title(self, conn: sqlite3.Connection) -> None:
        repo = TaskRepository(conn)
        repo.upsert(id="DRIVE-1234", title=None, first_seen_ts=100.0)
        task = repo.get("DRIVE-1234")
        assert task is not None
        assert task.title is None

    def test_get_missing_task(self, conn: sqlite3.Connection) -> None:
        repo = TaskRepository(conn)
        assert repo.get("MISSING") is None

    def test_get_all_returns_all_tasks(self, conn: sqlite3.Connection) -> None:
        repo = TaskRepository(conn)
        repo.upsert(id="A-1", title="alpha", first_seen_ts=1.0)
        repo.upsert(id="B-2", title="beta", first_seen_ts=2.0)
        tasks = repo.get_all()
        assert len(tasks) == 2
        ids = {t.id for t in tasks}
        assert ids == {"A-1", "B-2"}


class TestAppUsageRepositoryWithTask:
    def test_add_duration_with_task_id_creates_row(self, conn: sqlite3.Connection) -> None:
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)
        rows = conn.execute("SELECT * FROM app_usage").fetchall()
        assert len(rows) == 1
        assert rows[0][2] == "firefox"  # app_name
        assert rows[0][6] == "DRIVE-1"  # task_id

    def test_add_duration_same_app_different_task_creates_separate_rows(
        self, conn: sqlite3.Connection
    ) -> None:
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-2", duration_seconds=30)
        rows = conn.execute("SELECT * FROM app_usage").fetchall()
        assert len(rows) == 2
        task_ids = {r[6] for r in rows}
        assert task_ids == {"DRIVE-1", "DRIVE-2"}

    def test_add_duration_same_app_same_task_merges(self, conn: sqlite3.Connection) -> None:
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=30)
        rows = conn.execute("SELECT * FROM app_usage").fetchall()
        assert len(rows) == 1
        assert rows[0][4] == 90  # duration_seconds

    def test_add_duration_task_id_none_separate_from_task_rows(
        self, conn: sqlite3.Connection
    ) -> None:
        """Rows with task_id=NULL are separate from rows with a specific task_id."""
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id=None, duration_seconds=60)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=30)
        rows = conn.execute("SELECT * FROM app_usage").fetchall()
        assert len(rows) == 2

    def test_get_grouped_by_task_orders_by_total_duration(self, conn: sqlite3.Connection) -> None:
        """Within each task group, apps are ordered by duration_seconds DESC."""
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)
        repo.add_duration(activity_id=1, app_name="code", task_id="DRIVE-1", duration_seconds=300)
        repo.add_duration(activity_id=1, app_name="firefox", task_id=None, duration_seconds=100)

        groups = repo.get_grouped_by_task(1)
        assert len(groups) == 2
        # Group with task_id='DRIVE-1' has apps ordered by duration
        drive = [g for g in groups if g.task_id == "DRIVE-1"][0]
        assert [a.app_name for a in drive.apps] == ["code", "firefox"]
        # 'No task' group
        no_task = [g for g in groups if g.task_id is None][0]
        assert no_task.task_title is None
        assert [a.app_name for a in no_task.apps] == ["firefox"]

    def test_get_grouped_by_task_includes_title_from_task_table(
        self, conn: sqlite3.Connection
    ) -> None:
        repo_task = TaskRepository(conn)
        repo_task.upsert(id="DRIVE-1", title="Fix bug", first_seen_ts=1.0)
        repo_usage = AppUsageRepository(conn)
        repo_usage.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)

        groups = repo_usage.get_grouped_by_task(1)
        drive = [g for g in groups if g.task_id == "DRIVE-1"][0]
        assert drive.task_title == "Fix bug"

    def test_get_grouped_by_task_returns_no_task_group_for_null_rows(
        self, conn: sqlite3.Connection
    ) -> None:
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="konsole", task_id=None, duration_seconds=60)
        groups = repo.get_grouped_by_task(1)
        assert len(groups) == 1
        assert groups[0].task_id is None
        assert groups[0].task_title is None

    def test_get_grouped_by_task_empty(self, conn: sqlite3.Connection) -> None:
        repo = AppUsageRepository(conn)
        assert repo.get_grouped_by_task(99) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_repository_task.py -v`
Expected: FAIL with `ImportError: cannot import name 'TaskRepository'`

- [ ] **Step 3: Update `storage/repository.py`**

Replace the entire contents of `storage/repository.py` with:

```python
import logging
import sqlite3
import time

from models.app_usage import AppUsage
from models.task import Task, TaskGroup

logger = logging.getLogger(__name__)


class ActivityRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, activity) -> Activity:
        cursor = self._conn.execute(
            "INSERT INTO activity (name, icon_path, is_active, total_duration_seconds) VALUES (?, ?, ?, ?)",
            (activity.name, activity.icon_path, int(activity.is_active), activity.total_duration_seconds),
        )
        self._conn.commit()
        activity.id = cursor.lastrowid or 0
        return activity

    def get_all(self) -> list[Activity]:
        rows = self._conn.execute(
            "SELECT id, name, icon_path, is_active, total_duration_seconds FROM activity ORDER BY id"
        ).fetchall()
        return [
            Activity(id=r[0], name=r[1], icon_path=r[2], is_active=bool(r[3]), total_duration_seconds=r[4])
            for r in rows
        ]

    def get_by_id(self, activity_id: int) -> Activity | None:
        row = self._conn.execute(
            "SELECT id, name, icon_path, is_active, total_duration_seconds FROM activity WHERE id = ?",
            (activity_id,),
        ).fetchone()
        if row is None:
            return None
        return Activity(id=row[0], name=row[1], icon_path=row[2], is_active=bool(row[3]), total_duration_seconds=row[4])

    def get_active(self) -> Activity | None:
        row = self._conn.execute(
            "SELECT id, name, icon_path, is_active, total_duration_seconds FROM activity WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Activity(id=row[0], name=row[1], icon_path=row[2], is_active=bool(row[3]), total_duration_seconds=row[4])

    def set_all_inactive(self) -> None:
        self._conn.execute("UPDATE activity SET is_active = 0")
        self._conn.commit()

    def update(self, activity) -> None:
        self._conn.execute(
            "UPDATE activity SET name=?, icon_path=?, is_active=?, total_duration_seconds=? WHERE id=?",
            (activity.name, activity.icon_path, int(activity.is_active), activity.total_duration_seconds, activity.id),
        )
        self._conn.commit()

    def delete(self, activity_id: int) -> None:
        self._conn.execute("DELETE FROM activity WHERE id = ?", (activity_id,))
        self._conn.commit()


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, id: str, title: str | None, first_seen_ts: float) -> None:
        """Insert a task row if it does not exist. Never overwrites an existing title (first-seen wins)."""
        self._conn.execute(
            "INSERT OR IGNORE INTO task (id, title, first_seen_ts) VALUES (?, ?, ?)",
            (id, title, first_seen_ts),
        )
        self._conn.commit()

    def get(self, id: str) -> Task | None:
        row = self._conn.execute(
            "SELECT id, title, first_seen_ts FROM task WHERE id = ?", (id,)
        ).fetchone()
        if row is None:
            return None
        return Task(id=row[0], title=row[1], first_seen_ts=row[2])

    def get_all(self) -> list[Task]:
        rows = self._conn.execute(
            "SELECT id, title, first_seen_ts FROM task ORDER BY first_seen_ts"
        ).fetchall()
        return [Task(id=r[0], title=r[1], first_seen_ts=r[2]) for r in rows]


class AppUsageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, usage: AppUsage) -> AppUsage:
        now = time.time()
        row = self._conn.execute(
            "SELECT id, duration_seconds FROM app_usage"
            " WHERE activity_id=? AND app_name=? AND task_id IS ?",
            (usage.activity_id, usage.app_name, usage.task_id),
        ).fetchone()

        if row is not None:
            self._conn.execute(
                "UPDATE app_usage SET duration_seconds=?, window_title=?, last_seen_ts=? WHERE id=?",
                (usage.duration_seconds, usage.window_title, now, row[0]),
            )
            self._conn.commit()
            usage.id = row[0]
            usage.last_seen_ts = now
            return usage
        else:
            cursor = self._conn.execute(
                "INSERT INTO app_usage"
                " (activity_id, app_name, window_title, duration_seconds, last_seen_ts, task_id)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    usage.activity_id, usage.app_name, usage.window_title,
                    usage.duration_seconds, now, usage.task_id,
                ),
            )
            self._conn.commit()
            usage.id = cursor.lastrowid or 0
            usage.last_seen_ts = now
            return usage

    def get_by_activity(self, activity_id: int) -> list[AppUsage]:
        rows = self._conn.execute(
            "SELECT id, activity_id, app_name, window_title, duration_seconds, last_seen_ts, task_id"
            " FROM app_usage WHERE activity_id=? ORDER BY duration_seconds DESC",
            (activity_id,),
        ).fetchall()
        return [
            AppUsage(
                id=r[0], activity_id=r[1], app_name=r[2], window_title=r[3],
                duration_seconds=r[4], last_seen_ts=r[5], task_id=r[6],
            )
            for r in rows
        ]

    def add_duration(
        self, activity_id: int, app_name: str, duration_seconds: int,
        task_id: str | None = None,
    ) -> None:
        row = self._conn.execute(
            "SELECT id, duration_seconds FROM app_usage"
            " WHERE activity_id=? AND app_name=? AND task_id IS ?",
            (activity_id, app_name, task_id),
        ).fetchone()

        now = time.time()
        if row is not None:
            new_duration = row[1] + duration_seconds
            self._conn.execute(
                "UPDATE app_usage SET duration_seconds=?, last_seen_ts=? WHERE id=?",
                (new_duration, now, row[0]),
            )
        else:
            self._conn.execute(
                "INSERT INTO app_usage"
                " (activity_id, app_name, duration_seconds, last_seen_ts, task_id)"
                " VALUES (?, ?, ?, ?, ?)",
                (activity_id, app_name, duration_seconds, now, task_id),
            )
        self._conn.commit()

    def get_grouped_by_task(self, activity_id: int) -> list[TaskGroup]:
        """Return all app_usage rows for the activity, grouped by task_id, with task titles joined in.

        Includes a special group with task_id=None for rows where the task is unassigned.
        """
        rows = self._conn.execute(
            """
            SELECT a.id, a.activity_id, a.app_name, a.window_title,
                   a.duration_seconds, a.last_seen_ts, a.task_id,
                   t.title AS task_title
            FROM app_usage a
            LEFT JOIN task t ON t.id = a.task_id
            WHERE a.activity_id = ?
            ORDER BY a.task_id NULLS LAST, a.duration_seconds DESC
            """,
            (activity_id,),
        ).fetchall()

        groups: dict[str | None, TaskGroup] = {}
        order: list[str | None] = []
        for r in rows:
            usage = AppUsage(
                id=r[0], activity_id=r[1], app_name=r[2], window_title=r[3],
                duration_seconds=r[4], last_seen_ts=r[5], task_id=r[6],
            )
            key = r[6]  # task_id (or None)
            if key not in groups:
                groups[key] = TaskGroup(
                    task_id=key,
                    task_title=r[7],  # may be None
                    apps=(),
                )
                order.append(key)
            groups[key] = TaskGroup(
                task_id=key,
                task_title=r[7],
                apps=groups[key].apps + (usage,),
            )

        return [groups[k] for k in order]
```

**Note:** SQLite's `NULLS LAST` syntax requires SQLite 3.30+. CachyOS ships 3.4x; this works. If you want to be defensive, you can replace with a `CASE WHEN ... THEN 0 ELSE 1 END` expression. We'll keep the cleaner form; tests will catch any issue.

- [ ] **Step 4: Run the new test**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_repository_task.py -v`
Expected: 12 passed

- [ ] **Step 5: Verify existing repository tests still pass**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_repository.py tests/test_time_tracking.py tests/test_storage_service.py -v 2>&1 | tail -3`
Expected: all pass. The `add_duration` and `upsert` calls in existing tests don't pass `task_id`; the default `None` is applied.

- [ ] **Step 6: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check storage/repository.py tests/test_repository_task.py
MYPYPATH=. .venv/bin/mypy storage/repository.py
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add storage/repository.py tests/test_repository_task.py
git commit -m "feat: TaskRepository and AppUsageRepository with task_id"
```

---

## Task 6: StorageService exposes tasks

**Files:**
- Modify: `services/storage_service.py`

- [ ] **Step 1: Read existing tests and confirm signature**

`tests/test_storage_service.py` constructs `StorageService(":memory:")`. The only field it touches is `storage.activities` and `storage.app_usage`. No field is named `tasks`. So adding `self.tasks: TaskRepository` is purely additive.

- [ ] **Step 2: Update `services/storage_service.py`**

Replace the entire contents with:

```python
import logging
import sqlite3

from storage.repository import ActivityRepository, AppUsageRepository, TaskRepository
from storage.schema import initialize_schema

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        initialize_schema(self.conn)
        self.activities = ActivityRepository(self.conn)
        self.app_usage = AppUsageRepository(self.conn)
        self.tasks = TaskRepository(self.conn)
        logger.info("StorageService initialized (db=%s)", db_path)

    def reset_active(self) -> None:
        """Force all activities to inactive. Intended for application startup."""
        self.activities.set_all_inactive()
        logger.info("All activities reset to inactive on startup")
```

- [ ] **Step 3: Run all tests**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -q 2>&1 | tail -2`
Expected: 110 passed (98 + 9 from `test_schema_task.py` + 12 from `test_repository_task.py` — but some of those duplicate cases, so the count will be whatever it lands on; the key check is `passed`).

- [ ] **Step 4: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check services/storage_service.py
MYPYPATH=. .venv/bin/mypy services/storage_service.py
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add services/storage_service.py
git commit -m "feat: StorageService exposes TaskRepository"
```

---

## Task 7: ConfigService

**Files:**
- Create: `services/config_service.py`
- Test: `tests/test_config_service.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_service.py`:

```python
import json

import pytest

from services.config_service import (
    CONFIG_FILENAME,
    DEFAULT_CONFIG,
    ConfigService,
    find_project_root,
)
from services.task_detector import DEFAULT_TASK_ID_REGEX


def test_default_config_has_task_id_regex() -> None:
    assert "task_id_regex" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["task_id_regex"] == DEFAULT_TASK_ID_REGEX


def test_config_filename() -> None:
    assert CONFIG_FILENAME == "trackit.json"


def test_find_project_root_with_pyproject(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_walks_up(tmp_path) -> None:
    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert find_project_root(sub) == tmp_path


def test_find_project_root_falls_back_to_cwd(tmp_path, monkeypatch) -> None:
    """If no pyproject.toml is found, fall back to cwd."""
    monkeypatch.chdir(tmp_path)
    assert find_project_root(tmp_path / "nowhere") == tmp_path


class TestConfigService:
    def test_missing_file_is_created_with_default(self, tmp_path) -> None:
        service = ConfigService(project_root=tmp_path)
        path = tmp_path / CONFIG_FILENAME
        assert path.exists()
        data = json.loads(path.read_text())
        assert data == DEFAULT_CONFIG
        detector = service.task_detector
        assert detector.detect("DRIVE-1234") is not None

    def test_valid_custom_regex_is_loaded(self, tmp_path) -> None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps({"task_id_regex": r"#(\d+)"}))
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("Some title #42")
        assert result.task_id == "#42"

    def test_invalid_json_falls_back_to_default(self, tmp_path) -> None:
        path = tmp_path / CONFIG_FILENAME
        path.write_text("not valid json {{{")
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("DRIVE-1234")
        assert result.task_id == "DRIVE-1234"
        # File must NOT be overwritten
        assert path.read_text() == "not valid json {{{"

    def test_missing_task_id_regex_falls_back_to_default(self, tmp_path) -> None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps({"other_key": "value"}))
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("DRIVE-1234")
        assert result.task_id == "DRIVE-1234"

    def test_invalid_regex_falls_back_to_default(self, tmp_path) -> None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps({"task_id_regex": "(unclosed"}))
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("DRIVE-1234")
        assert result.task_id == "DRIVE-1234"

    def test_non_string_regex_falls_back_to_default(self, tmp_path) -> None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps({"task_id_regex": 123}))
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("DRIVE-1234")
        assert result.task_id == "DRIVE-1234"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_config_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.config_service'`

- [ ] **Step 3: Write the implementation**

Create `services/config_service.py`:

```python
import json
import logging
import re
from pathlib import Path

from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "trackit.json"

DEFAULT_CONFIG: dict[str, str] = {
    "task_id_regex": DEFAULT_TASK_ID_REGEX,
}


def find_project_root(start: Path) -> Path:
    """Walk up from `start` looking for pyproject.toml. Fall back to cwd if not found."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


class ConfigService:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._config_path = project_root / CONFIG_FILENAME
        self._task_id_regex: re.Pattern[str] = re.compile(DEFAULT_TASK_ID_REGEX)
        self._load()

    def _load(self) -> None:
        if not self._config_path.exists():
            try:
                self._config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
                logger.info("Created default config at %s", self._config_path)
            except OSError as exc:
                logger.warning(
                    "Failed to create config at %s: %s — using default regex",
                    self._config_path, exc,
                )
            return

        try:
            data = json.loads(self._config_path.read_text())
        except json.JSONDecodeError as exc:
            logger.warning(
                "Invalid JSON in %s: %s — using default regex",
                self._config_path, exc,
            )
            return

        if not isinstance(data, dict):
            logger.warning(
                "Config at %s is not an object — using default regex", self._config_path,
            )
            return

        pattern = data.get("task_id_regex")
        if not isinstance(pattern, str) or not pattern:
            logger.warning(
                "Missing/invalid task_id_regex in %s — using default", self._config_path,
            )
            return

        try:
            self._task_id_regex = re.compile(pattern)
            logger.info("Loaded task_id_regex from %s: %s", self._config_path, pattern)
        except re.error as exc:
            logger.warning(
                "Invalid regex in %s: %s — using default", self._config_path, exc,
            )

    @property
    def task_detector(self) -> TaskDetector:
        return TaskDetector(self._task_id_regex)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_config_service.py -v`
Expected: 11 passed

- [ ] **Step 5: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check services/config_service.py tests/test_config_service.py
MYPYPATH=. .venv/bin/mypy services/config_service.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add services/config_service.py tests/test_config_service.py
git commit -m "feat: ConfigService loads task_id_regex from trackit.json"
```

---

## Task 8: TimeTrackingService task detection

**Files:**
- Modify: `services/time_tracking.py`
- Test: `tests/test_time_tracking_task.py`
- Update: `tests/test_time_tracking.py` (signature change)

- [ ] **Step 1: Write the failing test**

Create `tests/test_time_tracking_task.py`:

```python
import re
from unittest.mock import MagicMock

import pytest

from models.window_info import WindowInfo
from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService


@pytest.fixture
def services():
    storage = StorageService(":memory:")
    window_tracker = WindowTrackerService()
    activity_service = ActivityService(storage)
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    time_tracking = TimeTrackingService(
        storage, window_tracker, activity_service, detector
    )
    return storage, window_tracker, activity_service, time_tracking


def _emit(window_tracker: WindowTrackerService, app: str, title: str) -> None:
    window_tracker.window_changed.emit(WindowInfo(app_name=app, window_title=title, pid=None))


def test_task_change_flushes_segment_under_old_task(services) -> None:
    """firefox on 'no task' title, then on 'DRIVE-1' title — the previous segment is under no task."""
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _emit(window_tracker, "firefox", "Stack Overflow")  # no task
    _emit(window_tracker, "firefox", "DRIVE-1 - fix bug")  # has task

    usages = storage.app_usage.get_by_activity(activity.id)
    no_task = [u for u in usages if u.app_name == "firefox" and u.task_id is None]
    with_task = [u for u in usages if u.app_name == "firefox" and u.task_id == "DRIVE-1"]
    assert len(no_task) == 1
    assert len(with_task) == 1


def test_task_change_does_not_flush_when_unchanged(services) -> None:
    """firefox stays on the same task across window_changed events — no new row."""
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _emit(window_tracker, "firefox", "DRIVE-1 - first")
    _emit(window_tracker, "firefox", "DRIVE-1 - second")

    usages = storage.app_usage.get_by_activity(activity.id)
    assert len(usages) == 1
    assert usages[0].task_id == "DRIVE-1"


def test_task_change_records_new_task(services) -> None:
    """firefox on DRIVE-1 then DRIVE-2 — both rows exist."""
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _emit(window_tracker, "firefox", "DRIVE-1 - first")
    _emit(window_tracker, "firefox", "DRIVE-2 - second")

    usages = storage.app_usage.get_by_activity(activity.id)
    task_ids = {u.task_id for u in usages}
    assert task_ids == {"DRIVE-1", "DRIVE-2"}


def test_task_change_to_no_task_creates_separate_row(services) -> None:
    """firefox on task, then no task — distinct rows."""
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _emit(window_tracker, "firefox", "DRIVE-1 - first")
    _emit(window_tracker, "firefox", "Stack Overflow")

    usages = storage.app_usage.get_by_activity(activity.id)
    assert len(usages) == 2
    assert {u.task_id for u in usages} == {"DRIVE-1", None}


def test_task_upserted_on_first_sight(services) -> None:
    """First time a task_id is seen, the task row is created with the first-seen title."""
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _emit(window_tracker, "firefox", "Fix login bug : DRIVE-1234")
    _emit(window_tracker, "firefox", "Fix login bug : DRIVE-1234")
    _emit(window_tracker, "code", "DRIVE-1234: another file")

    task = storage.tasks.get("DRIVE-1234")
    assert task is not None
    assert task.title == "Fix login bug"  # first-seen wins

    usages = storage.app_usage.get_by_activity(activity.id)
    assert all(u.task_id == "DRIVE-1234" for u in usages)


def test_current_task_id_property(services) -> None:
    """current_task_id returns the active task's ID, or None."""
    _, window_tracker, _, time_tracking = services
    _emit(window_tracker, "firefox", "DRIVE-1 - x")
    assert time_tracking.current_task_id == "DRIVE-1"
    _emit(window_tracker, "firefox", "Stack Overflow")
    assert time_tracking.current_task_id is None


def test_activity_switch_resets_current_task(services) -> None:
    """On activity switch, the current task is cleared."""
    storage, window_tracker, activity_service, time_tracking = services
    activity1 = activity_service.create_activity("Work")
    activity_service.set_active(activity1.id)
    _emit(window_tracker, "firefox", "DRIVE-1 - x")
    assert time_tracking.current_task_id == "DRIVE-1"

    activity2 = activity_service.create_activity("Study")
    activity_service.set_active(activity2.id)
    assert time_tracking.current_task_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_time_tracking_task.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'detector'`

- [ ] **Step 3: Update `services/time_tracking.py`**

Replace the entire contents of `services/time_tracking.py` with:

```python
import logging
import time

from PySide6.QtCore import QObject

from models.activity import Activity
from models.task_key import TaskKey
from models.window_info import WindowInfo
from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.task_detector import TaskDetector
from services.window_tracker import WindowTrackerService

logger = logging.getLogger(__name__)


class TimeTrackingService(QObject):
    def __init__(
        self,
        storage: StorageService,
        window_tracker: WindowTrackerService,
        activity_service: ActivityService,
        detector: TaskDetector,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._window_tracker = window_tracker
        self._activity_service = activity_service
        self._detector = detector
        self._segment_start: float = 0.0
        self._current_window: WindowInfo | None = None
        self._current_task: TaskKey | None = None
        self._active_activity: Activity | None = None

        window_tracker.window_changed.connect(self._on_window_changed)
        activity_service.active_activity_changed.connect(self._on_activity_changed)
        logger.info("TimeTrackingService initialized")

    @property
    def current_segment_seconds(self) -> int:
        if self._segment_start <= 0:
            return 0
        return max(0, int(time.time() - self._segment_start))

    @property
    def current_task_id(self) -> str | None:
        return self._current_task.task_id if self._current_task is not None else None

    def _on_window_changed(self, window_info: WindowInfo) -> None:
        now = time.time()
        new_task = self._detector.detect(window_info.window_title)

        if self._current_window is not None and self._segment_start > 0:
            task_changed = new_task != self._current_task
            window_changed = window_info.app_name != self._current_window.app_name
            if task_changed or window_changed:
                duration = int(now - self._segment_start)
                self._record_usage(self._current_window, duration, self._active_activity)

        self._current_window = window_info
        self._current_task = new_task
        self._segment_start = now

    def _on_activity_changed(self, activity: Activity | None) -> None:
        if self._current_window is not None and self._segment_start > 0:
            now = time.time()
            duration = int(now - self._segment_start)
            self._record_usage(self._current_window, duration, self._active_activity)
        self._segment_start = time.time()
        self._current_task = None
        self._active_activity = activity

    def _record_usage(
        self, window_info: WindowInfo, duration: int, activity: Activity | None = None
    ) -> None:
        active_activity = activity or self._activity_service.get_active_activity()
        if active_activity is None:
            return

        task_id = self._current_task.task_id if self._current_task is not None else None
        if task_id is not None:
            self._storage.tasks.upsert(
                id=task_id,
                title=self._current_task.task_title,
                first_seen_ts=time.time(),
            )

        self._storage.app_usage.add_duration(
            activity_id=active_activity.id,
            app_name=window_info.app_name,
            task_id=task_id,
            duration_seconds=duration,
        )

        active_activity.total_duration_seconds += duration
        self._storage.activities.update(active_activity)

        logger.debug(
            "Recorded %ds for %s (task=%s) under activity %s",
            duration, window_info.app_name, task_id, active_activity.name,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_time_tracking_task.py -v`
Expected: 7 passed

- [ ] **Step 5: Update the existing `tests/test_time_tracking.py`**

The existing fixture constructs `TimeTrackingService(storage, window_tracker, activity_service)` with no detector. Update it to pass one:

Read `tests/test_time_tracking.py` and replace the fixture (lines 9-15):

```python
@pytest.fixture
def services() -> tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService]:
    import re
    from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector
    storage = StorageService(":memory:")
    window_tracker = WindowTrackerService()
    activity_service = ActivityService(storage)
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    time_tracking = TimeTrackingService(storage, window_tracker, activity_service, detector)
    return storage, window_tracker, activity_service, time_tracking
```

(The import is inline to keep the diff minimal.)

- [ ] **Step 6: Run the existing time_tracking tests**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_time_tracking.py -v`
Expected: 5 passed.

- [ ] **Step 7: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check services/time_tracking.py tests/test_time_tracking.py tests/test_time_tracking_task.py
MYPYPATH=. .venv/bin/mypy services/time_tracking.py
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add services/time_tracking.py tests/test_time_tracking.py tests/test_time_tracking_task.py
git commit -m "feat: TimeTrackingService flushes segments on task change"
```

---

## Task 9: create_services accepts detector

**Files:**
- Modify: `core/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Update `core/app.py`**

Replace the `create_services` function and the body of `main()`. The rest of the file stays the same. Read the file and replace just the relevant block.

The full updated `core/app.py` (only the changed parts shown; rest of the file is unchanged):

```python
# At the top, in the import block, add:
from pathlib import Path

from services.config_service import ConfigService, find_project_root
from services.task_detector import TaskDetector
from services.time_tracking import TimeTrackingService
```

Wait — the imports for `TimeTrackingService` and `StorageService` already exist. Add only `ConfigService`, `find_project_root`, `TaskDetector`, and `Path`.

The updated `create_services`:

```python
def create_services(
    storage: StorageService, detector: TaskDetector,
) -> tuple[WindowTrackerService, ActivityService, TimeTrackingService]:
    window_tracker = WindowTrackerService()
    activity_service = ActivityService(storage)
    time_tracking = TimeTrackingService(storage, window_tracker, activity_service, detector)
    return window_tracker, activity_service, time_tracking
```

The updated `main()`:

```python
def main() -> None:
    app = create_app()
    db_path = get_db_path()
    logger.info("Starting TrackIt (db=%s)", db_path)

    storage = StorageService(db_path)

    project_root = find_project_root(Path(__file__).resolve().parent)
    config = ConfigService(project_root)
    detector = config.task_detector

    window_tracker, activity_service, time_tracking = create_services(storage, detector)

    storage.reset_active()

    app_info_service = AppInfoService(window_tracker)

    _register_dbus_handler(window_tracker)

    from ui.main_window import MainWindow
    window = MainWindow(activity_service, window_tracker, storage, time_tracking, app_info_service)
    window.show()

    window_tracker.start()

    exit_code = app.exec()
    window_tracker.stop()
    app_info_service.stop()
    logger.info("TrackIt exiting (code=%d)", exit_code)
    sys.exit(exit_code)
```

**Implementation steps for the editor:**

1. Read `core/app.py` and add the new imports in alphabetical order in the import block.
2. Replace the existing `create_services` definition with the new one.
3. Replace the body of `main()` (the block from `storage = StorageService(db_path)` through `time_tracking = create_services(storage)`) with the new code.

- [ ] **Step 2: Update `tests/test_app.py`**

Read `tests/test_app.py` and update the calls to `create_services` to pass a detector:

```python
import re

from core.app import create_services
from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector


def test_create_services_returns_all_three() -> None:
    storage = ...
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    window_tracker, activity_service, time_tracking = create_services(storage, detector)
    ...
```

Read the file to see the actual structure; preserve the test names and assertions, but add the `detector` argument.

- [ ] **Step 3: Run the test**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_app.py -v`
Expected: 2 passed.

- [ ] **Step 4: Run the full test suite**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -q 2>&1 | tail -2`
Expected: all pass. (The current count is 110+; add ~7 from `test_time_tracking_task.py` minus any duplicates.)

- [ ] **Step 5: Smoke-import the bootstrap path**

Run: `MYPYPATH=. .venv/bin/python -c "from core.app import main; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check .
MYPYPATH=. .venv/bin/mypy
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add core/app.py tests/test_app.py
git commit -m "feat: create_services and main() thread detector through"
```

---

## Task 10: ActivityDetailWidget renders tasks as a tree

**Files:**
- Modify: `ui/activity_detail.py`
- Test: `tests/test_ui_activity_detail_tasks.py`
- Update: `tests/test_ui_activity_detail.py` (rename `_usage_list` to `_tree` in assertions)

- [ ] **Step 1: Read existing test_ui_activity_detail.py to understand the API surface**

The existing tests access `widget._usage_list.count()`, `widget._usage_list.item(0)`, `widget.show_activity(id)`, `widget._activity_service`, `widget._storage`. We'll rename `_usage_list` to `_tree` (a `QTreeWidget`).

- [ ] **Step 2: Update the existing `tests/test_ui_activity_detail.py`**

Read the file and replace `widget._usage_list` with `widget._tree` (and adjust the assertion that used `count()` and `item(0)` if needed — `QTreeWidget` has different methods: `topLevelItemCount()`, `topLevelItem(i)`, `child(i).text(0)`, etc.).

The updated test `test_show_activity_shows_app_usage`:

```python
def test_show_activity_shows_app_usage(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.app_usage.add_duration(activity.id, "firefox", 3600)
    widget.show_activity(activity.id)
    # "No task" group has 1 child: firefox
    assert widget._tree.topLevelItemCount() == 1
    no_task = widget._tree.topLevelItem(0)
    assert no_task.childCount() == 1
    assert "firefox" in no_task.child(0).text(0)
```

Adjust the other tests similarly: replace `widget._usage_list` with `widget._tree`, replacing `count()` and `item(i)` with `topLevelItemCount()` and `topLevelItem(i)` as needed.

- [ ] **Step 3: Run the updated existing test to confirm it fails**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_ui_activity_detail.py -v`
Expected: FAIL on `AttributeError: 'ActivityDetailWidget' object has no attribute '_tree'`

- [ ] **Step 4: Write the new task-related UI tests**

Create `tests/test_ui_activity_detail_tasks.py`:

```python
import pytest

from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector
import re
from ui.activity_detail import ActivityDetailWidget


@pytest.fixture
def widget(qtbot) -> ActivityDetailWidget:
    storage = StorageService(":memory:")
    service = ActivityService(storage)
    w = ActivityDetailWidget(service, storage)
    qtbot.addWidget(w)
    return w


def test_no_task_group_renders_when_only_null_task_rows(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.app_usage.add_duration(activity.id, "konsole", 60, task_id=None)
    widget.show_activity(activity.id)
    # 1 top-level group: "No task"
    assert widget._tree.topLevelItemCount() == 1
    label = widget._tree.topLevelItem(0).text(0)
    assert "No task" in label
    assert widget._tree.topLevelItem(0).childCount() == 1
    assert "konsole" in widget._tree.topLevelItem(0).child(0).text(0)


def test_task_group_renders_with_title_and_apps(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.tasks.upsert(id="DRIVE-1", title="Fix bug", first_seen_ts=1.0)
    widget._storage.app_usage.add_duration(
        activity.id, "firefox", 60, task_id="DRIVE-1"
    )
    widget._storage.app_usage.add_duration(
        activity.id, "code", 120, task_id="DRIVE-1"
    )
    widget.show_activity(activity.id)

    # 1 top-level group: "Tasks"
    assert widget._tree.topLevelItemCount() == 1
    tasks_group = widget._tree.topLevelItem(0)
    assert "Tasks" in tasks_group.text(0)
    # 1 task child, 2 apps
    assert tasks_group.childCount() == 1
    drive = tasks_group.child(0)
    assert "DRIVE-1" in drive.text(0)
    assert "Fix bug" in drive.text(0)
    assert drive.childCount() == 2
    # Apps ordered by duration DESC
    assert "code" in drive.child(0).text(0)
    assert "firefox" in drive.child(1).text(0)


def test_both_groups_render_when_mixed(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.tasks.upsert(id="DRIVE-1", title="Fix bug", first_seen_ts=1.0)
    widget._storage.app_usage.add_duration(
        activity.id, "firefox", 60, task_id="DRIVE-1"
    )
    widget._storage.app_usage.add_duration(
        activity.id, "konsole", 30, task_id=None
    )
    widget.show_activity(activity.id)
    assert widget._tree.topLevelItemCount() == 2
    labels = [
        widget._tree.topLevelItem(i).text(0)
        for i in range(widget._tree.topLevelItemCount())
    ]
    assert any("Tasks" in l for l in labels)
    assert any("No task" in l for l in labels)


def test_task_label_omits_title_when_none(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.tasks.upsert(id="DRIVE-1", title=None, first_seen_ts=1.0)
    widget._storage.app_usage.add_duration(
        activity.id, "firefox", 60, task_id="DRIVE-1"
    )
    widget.show_activity(activity.id)
    drive = widget._tree.topLevelItem(0).child(0)
    assert "DRIVE-1" in drive.text(0)
    assert "—" not in drive.text(0) or "—" in drive.text(0)  # the title-with-em-dash form
    # When title is None, the label is "DRIVE-1 — 1m" (with em-dash, no title part)
```

- [ ] **Step 5: Run the new tests to confirm they fail**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_ui_activity_detail_tasks.py -v`
Expected: FAIL on `AttributeError: 'ActivityDetailWidget' object has no attribute '_tree'`

- [ ] **Step 6: Replace `ui/activity_detail.py`**

Replace the entire contents of `ui/activity_detail.py` with:

```python
import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.activity import Activity
from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService
from ui.format import format_duration

logger = logging.getLogger(__name__)

TASKS_GROUP_LABEL = "Tasks"
NO_TASK_GROUP_LABEL = "No task"
TASK_TITLE_SEPARATOR = " — "


class ActivityDetailWidget(QWidget):
    def __init__(
        self,
        activity_service: ActivityService,
        storage: StorageService,
        time_tracking: TimeTrackingService | None = None,
        window_tracker: WindowTrackerService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._activity_service = activity_service
        self._storage = storage
        self._time_tracking = time_tracking
        self._window_tracker = window_tracker
        self._current_activity_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._name_label = QLabel("Select an Activity")
        self._name_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 4px 0;")
        layout.addWidget(self._name_label)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(1)
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet("font-size: 14px;")
        self._tree.setRootIsDecorated(False)
        layout.addWidget(self._tree)

        self._activity_service.activity_updated.connect(self._on_activity_updated)
        self._activity_service.activity_deleted.connect(self._on_activity_deleted)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._periodic_refresh)
        self._refresh_timer.start(1000)

    def show_activity(self, activity_id: int) -> None:
        activity = self._activity_service._storage.activities.get_by_id(activity_id)
        if activity is None:
            return
        self._current_activity_id = activity_id
        self._update_header(activity)
        self._refresh_usage()

    def _update_header(self, activity: Activity) -> None:
        self._name_label.setText(activity.name)

    def _refresh_usage(self) -> None:
        self._tree.clear()
        if self._current_activity_id is None:
            return

        groups = self._storage.app_usage.get_grouped_by_task(self._current_activity_id)
        active_activity = self._activity_service.get_active_activity()
        current_app: str | None = None
        current_task: str | None = None
        if self._window_tracker is not None and self._window_tracker.current_window is not None:
            current_app = self._window_tracker.current_window.app_name
        if self._time_tracking is not None:
            current_task = self._time_tracking.current_task_id

        with_task_groups = [g for g in groups if g.task_id is not None]
        no_task_groups = [g for g in groups if g.task_id is None]

        if with_task_groups:
            tasks_root = QTreeWidgetItem([TASKS_GROUP_LABEL])
            self._tree.addTopLevelItem(tasks_root)
            for group in with_task_groups:
                group_total = sum(a.duration_seconds for a in group.apps)
                title_part = (
                    f" {group.task_title}" if group.task_title else ""
                )
                task_label = (
                    f"{group.task_id}{title_part} {TASK_TITLE_SEPARATOR} "
                    f"{format_duration(group_total)}"
                )
                task_item = QTreeWidgetItem([task_label])
                tasks_root.addChild(task_item)
                for usage in group.apps:
                    is_current = self._is_current(
                        usage, active_activity, current_app, current_task
                    )
                    duration = usage.duration_seconds
                    if is_current and self._time_tracking is not None:
                        duration += self._time_tracking.current_segment_seconds
                    app_label = f"{usage.app_name}  —  {format_duration(duration)}"
                    app_item = QTreeWidgetItem([app_label])
                    if is_current:
                        app_item.setForeground(0, QColor("#c0a000"))
                    task_item.addChild(app_item)
            tasks_root.setExpanded(True)

        if no_task_groups:
            no_task_root = QTreeWidgetItem([NO_TASK_GROUP_LABEL])
            self._tree.addTopLevelItem(no_task_root)
            for group in no_task_groups:
                for usage in group.apps:
                    is_current = self._is_current(
                        usage, active_activity, current_app, current_task
                    )
                    duration = usage.duration_seconds
                    if is_current and self._time_tracking is not None:
                        duration += self._time_tracking.current_segment_seconds
                    app_label = f"{usage.app_name}  —  {format_duration(duration)}"
                    app_item = QTreeWidgetItem([app_label])
                    if is_current:
                        app_item.setForeground(0, QColor("#c0a000"))
                    no_task_root.addChild(app_item)
            no_task_root.setExpanded(True)

    def _is_current(
        self,
        usage,
        active_activity: Activity | None,
        current_app: str | None,
        current_task: str | None,
    ) -> bool:
        return (
            active_activity is not None
            and active_activity.id == self._current_activity_id
            and current_app == usage.app_name
            and current_task == usage.task_id
        )

    def _periodic_refresh(self) -> None:
        if self._current_activity_id is not None:
            self._refresh_usage()

    def _on_activity_updated(self, activity: Activity) -> None:
        if activity.id == self._current_activity_id:
            self._refresh_usage()

    def _on_activity_deleted(self, activity_id: int) -> None:
        if activity_id == self._current_activity_id:
            self._current_activity_id = None
            self._name_label.setText("Select an Activity")
            self._tree.clear()
```

- [ ] **Step 7: Run the new tests**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_ui_activity_detail_tasks.py tests/test_ui_activity_detail.py -v`
Expected: 8+ tests passed (4 new + 4 existing, after the rename).

- [ ] **Step 8: Run the full test suite**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -q 2>&1 | tail -2`
Expected: all pass.

- [ ] **Step 9: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check ui/activity_detail.py tests/test_ui_activity_detail.py tests/test_ui_activity_detail_tasks.py
MYPYPATH=. .venv/bin/mypy ui/activity_detail.py
```

Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add ui/activity_detail.py tests/test_ui_activity_detail.py tests/test_ui_activity_detail_tasks.py
git commit -m "feat: ActivityDetailWidget renders tasks in a QTreeWidget"
```

---

## Task 11: Final verification + push

**Files:** none modified

- [ ] **Step 1: Run the full verification suite**

```bash
.venv/bin/ruff check .
MYPYPATH=. .venv/bin/mypy
MYPYPATH=. .venv/bin/python -m pytest tests/ -v
```

Expected: no errors; all tests pass.

- [ ] **Step 2: Smoke-import the bootstrap path**

```bash
MYPYPATH=. .venv/bin/python -c "from core.app import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Confirm branch state and push**

```bash
git status
git log --oneline 57546fe..HEAD
git push -u origin feat/task-detection
```

Expected: working tree clean; ~10 commits ahead of main; branch pushed.

- [ ] **Step 4: Confirm the push**

```bash
git log --oneline -1 origin/feat/task-detection
```

Expected: matches `HEAD`.

---

## Self-Review (writer)

After writing this plan, I checked:

1. **Spec coverage:**
   - Schema: ✓ Task 3 (table, column, index, version).
   - Detection: ✓ Tasks 1, 2, 7 (TaskKey, TaskDetector, ConfigService).
   - Time tracking flush on task change: ✓ Task 8.
   - StorageService.tasks accessor: ✓ Task 6.
   - Right pane tree re-render: ✓ Task 10.
   - create_services / main wiring: ✓ Task 9.
   - First-seen task title: ✓ Task 5 (`TaskRepository.upsert` uses `INSERT OR IGNORE`).
   - "No task" group: ✓ Task 10 (explicit branch).
   - Live segment on `(app, task)`: ✓ Task 8 (`current_task_id` property) + Task 10 (`_is_current` matches both).
   - Activity switch resets task: ✓ Task 8 (`_on_activity_changed` clears `_current_task`).
   - Tests for all of the above: ✓ distributed across all tasks.

2. **Placeholder scan:** No "TBD" or "TODO" in any step. Code is shown for every code-touching step.

3. **Type consistency:**
   - `TaskKey` has `task_id: str | None`, `task_title: str | None` — used in `TaskDetector.detect`, `TimeTrackingService._current_task`, `_on_window_changed`, `_on_activity_changed`, `_record_usage`. Consistent.
   - `TaskDetector.__init__(self, regex: re.Pattern[str])` — used in `ConfigService.task_detector` property and in `tests/test_time_tracking_task.py`. Consistent.
   - `TaskRepository.upsert(self, id: str, title: str | None, first_seen_ts: float)` — used in `TimeTrackingService._record_usage` (with `task_id` and `task_title` from `TaskKey`). Consistent.
   - `AppUsageRepository.add_duration(self, activity_id, app_name, duration_seconds, task_id=None)` — called from `TimeTrackingService._record_usage` and from existing tests (no `task_id`, defaults to `None`). Consistent.
   - `TimeTrackingService.__init__(self, storage, window_tracker, activity_service, detector, parent=None)` — used in `core/app.py:create_services`, in `tests/test_time_tracking_task.py`, in updated `tests/test_time_tracking.py`. Consistent.
   - `create_services(storage, detector)` — used in `core/app.py:main` and in `tests/test_app.py`. Consistent.
   - `ActivityDetailWidget._tree` (QTreeWidget) — used in updated `tests/test_ui_activity_detail.py` and `tests/test_ui_activity_detail_tasks.py`. Consistent.

No issues found.
