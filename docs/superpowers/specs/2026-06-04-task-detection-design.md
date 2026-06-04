# Task Detection from Window Title — Design

**Date:** 2026-06-04
**Status:** Approved
**Scope:** Feature #2 of 3 (default pause / task detection / debug panel)

## Goal

Extract a task identifier (e.g. `DRIVE-1234`) from the active window's title and use it to group the per-app time tracking in the right pane. The user works on many tickets per day; the right pane currently lumps all `firefox` time into one row, making it hard to see which ticket was actually worked on. After this change, the same app under different tasks gets separate rows.

The detection is **configurable via a JSON file in the project root** so the user can tune the regex for their ticketing system (YouTrack, Jira, GitLab, etc.) without touching code.

## Background

The current schema (`storage/schema.py`, `SCHEMA_VERSION=1`) has one `app_usage` row per `(activity_id, app_name)`. A new dimension — `task_id` — must be added. The right pane (`ui/activity_detail.py`) currently shows a flat `QListWidget` of `app_name — duration`. The window title is currently stored on `app_usage` for reference but not parsed.

A real-world title looks like `Rewrite-update-price-logic-to-websockets-and-jobs : DRIVEO-4298`. The user wants both the ID (`DRIVEO-4298`) and a short human-readable title (`Rewrite-update-price-logic-to-websockets-and-jobs`) shown together in the right pane.

## Architecture

```
KWin D-Bus → WindowTrackerService
                ↓
            window_changed(WindowInfo{app_name, window_title})
                ↓
            TimeTrackingService._on_window_changed:
                task = ConfigService.detector.detect(window_title)
                if previous_task != current_task (or window changed):
                    flush old segment
                start new segment under current task
                ↓
            storage.app_usage.add_duration(
                activity_id, app_name, task_id, duration_seconds
            )

On first sight of a new task_id:
    storage.tasks.upsert(id=task_id, title=task_title, first_seen_ts=now)
    (do NOT overwrite an existing task.title)

Right pane read path:
    storage.app_usage.get_grouped_by_task(activity_id)
        → list[TaskGroup{task_id, task_title, apps}]
        → render in QTreeWidget with "Tasks" + "No task" groups
```

The detector is a pure function on the `TaskDetector` class. The `ConfigService` is the lifecycle owner. The `TimeTrackingService` is the integration point — it gains one new field (`_current_task`) and a new flush condition. The right pane is reshaped from a `QListWidget` to a `QTreeWidget` with two top-level groups.

## Data Model

### New table `task`

```sql
CREATE TABLE task (
    id TEXT PRIMARY KEY,        -- the task ID itself, e.g. "DRIVE-1234"
    title TEXT,                 -- first-seen window-title prefix, e.g. "Rewrite-..."
    first_seen_ts REAL NOT NULL
);
```

The task ID is the natural primary key. There is no separate numeric surrogate. The `title` is captured on first sight and never updated.

### `app_usage` gains one column

```sql
ALTER TABLE app_usage ADD COLUMN task_id TEXT REFERENCES task(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_app_usage_activity_task ON app_usage(activity_id, task_id);
```

Row identity becomes `(activity_id, app_name, task_id)`. Two rows may now share `(activity_id, app_name)` if they differ in `task_id`. Existing rows from before the migration all have `task_id = NULL` and live in the "No task" group.

### Schema version + migration

`SCHEMA_VERSION` becomes 2. A new `migrate_v1_to_v2(conn)` runs once, gated by `PRAGMA user_version`. It does:
1. `CREATE TABLE task (...)` (idempotent with `IF NOT EXISTS`).
2. `ALTER TABLE app_usage ADD COLUMN task_id TEXT REFERENCES task(id) ON DELETE SET NULL` (SQLite raises if column exists; the migration is gated by `user_version`, so it only runs once).
3. `PRAGMA user_version = 2`.

`initialize_schema(conn)` becomes the dispatcher: it reads `PRAGMA user_version`, applies missing migrations, then runs the current schema as a safety net.

## Detection

### `services/task_detector.py` (pure functions, no QObject)

```python
DEFAULT_TASK_ID_REGEX = r"\b([A-Z][A-Z0-9]+-\d+)\b"

@dataclass(frozen=True)
class TaskKey:
    task_id: str | None
    task_title: str | None

class TaskDetector:
    def __init__(self, regex: re.Pattern[str]) -> None:
        self._regex = regex

    def detect(self, window_title: str | None) -> TaskKey:
        if not window_title:
            return TaskKey(None, None)
        match = self._regex.search(window_title)
        if match is None:
            return TaskKey(None, None)
        task_id = match.group(1)
        prefix = window_title[: match.start()].rstrip(": \t-")
        task_title = prefix or None
        return TaskKey(task_id, task_title)
```

Behavior:
- `None` or empty title → `TaskKey(None, None)`.
- No regex match → `TaskKey(None, None)`.
- Match found → `TaskKey(task_id, task_title)`. Title is the substring before the match, stripped of trailing `:` / space / tab / dash. If the result is empty, `task_title = None` (we keep the ID).
- Multiple matches in one title → first match wins.

### `services/config_service.py` (no QObject, no signals)

```python
CONFIG_FILENAME = "trackit.json"
DEFAULT_CONFIG = {"task_id_regex": DEFAULT_TASK_ID_REGEX}

class ConfigService:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._config_path = project_root / CONFIG_FILENAME
        self._task_id_regex: re.Pattern[str] = re.compile(DEFAULT_TASK_ID_REGEX)
        self._load()

    def _load(self) -> None:
        if not self._config_path.exists():
            self._config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
            logger.info("Created default config at %s", self._config_path)
            return
        try:
            data = json.loads(self._config_path.read_text())
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON in %s: %s — using default regex", self._config_path, exc)
            return
        pattern = data.get("task_id_regex")
        if not isinstance(pattern, str) or not pattern:
            logger.warning("Missing/invalid task_id_regex in %s — using default", self._config_path)
            return
        try:
            self._task_id_regex = re.compile(pattern)
        except re.error as exc:
            logger.warning("Invalid regex in %s: %s — using default", self._config_path, exc)

    @property
    def task_detector(self) -> TaskDetector:
        return TaskDetector(self._task_id_regex)
```

`project_root` is the directory containing `pyproject.toml`. Found in `core/app.py` by walking up from `Path(__file__).resolve()` until a `pyproject.toml` is found. If not found, fall back to `Path.cwd()`.

If the file is missing, it is auto-created with the default. If it is invalid (bad JSON or bad regex), the existing file is left untouched and a warning is logged; the default regex is used for the session.

## Time Tracking Integration

`TimeTrackingService` gains one constructor parameter (`detector: TaskDetector`) and one private field (`_current_task: TaskKey | None`).

### `_on_window_changed(window_info: WindowInfo)`

```python
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
```

The previous segment is flushed when **either** the window changes (today's behavior) **or** the task changes (new behavior). This matches the user's example: firefox on a "no task" title for 3 min, then user navigates to a ticket — the 3 min stays under "no task", a new row starts at 0 under the new task.

### `_on_activity_changed(activity: Activity | None)`

Same as today, but additionally resets `self._current_task = None` after the flush. A new activity starts with no task attribution until the next `window_changed` arrives.

### `_record_usage`

```python
def _record_usage(self, window_info, duration, activity=None) -> None:
    active_activity = activity or self._activity_service.get_active_activity()
    if active_activity is None:
        return
    task_id = self._current_task.task_id if self._current_task else None
    self._storage.app_usage.add_duration(
        activity_id=active_activity.id,
        app_name=window_info.app_name,
        task_id=task_id,
        duration_seconds=duration,
    )
    active_activity.total_duration_seconds += duration
    self._storage.activities.update(active_activity)
```

### First-sight task insert

`storage.tasks.upsert(id=task_id, title=task_title, first_seen_ts=now)` is called from `TimeTrackingService` when the new task_id is not None. The `upsert` is `INSERT OR IGNORE` — never overwrites the existing title.

```python
def _record_usage(self, window_info, duration, activity=None) -> None:
    active_activity = activity or self._activity_service.get_active_activity()
    if active_activity is None:
        return
    task_id = self._current_task.task_id if self._current_task else None
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
    ...
```

## UI: `ActivityDetailWidget` re-render

Replace the `QListWidget` with a `QTreeWidget` with two top-level invisible-root children:

1. **"Tasks"** — a child per `task_id` found in the activity's `app_usage`. Each task child has its apps as grandchildren. Task label: `DRIVE-1234 — Rewrite-update-price-logic-to-websockets-and-jobs — 12m`. If title is None: `DRIVE-1234 — 12m`.
2. **"No task"** — apps with `task_id IS NULL` for this activity. Same per-app rows underneath, but no task header.

The `QTreeWidget` is set to expand all on update and not show column headers (single column). The "Tasks" and "No task" group labels are rendered as top-level items, with the apps as children (one indent level). The currently-active `(app, task)` row (live segment) gets a yellow `#c0a000` foreground, same as today.

A new repository method:

```python
def get_grouped_by_task(self, activity_id: int) -> list[TaskGroup]: ...
```

`TaskGroup` is a small dataclass:

```python
@dataclass(frozen=True)
class TaskGroup:
    task_id: str | None
    task_title: str | None
    apps: list[AppUsage]
```

The query groups `app_usage` by `task_id` and joins `task` for the title. The "No task" group is included as one of the returned items (with `task_id = None`).

### Live segment

`TimeTrackingService` exposes one new read-only property:

```python
@property
def current_task_id(self) -> str | None: ...
```

The right pane's `_refresh_usage` matches the current row by `(app_name == current_app and task_id == current_task_id)`, where `current_task_id` may be None.

**Note:** The right pane's live-segment visibility follows the existing (no-task) behavior — the row is created and starts accumulating only on the first `_record_usage` flush for that `(activity, app, task)` triple, which happens when the user switches *away* from it. If the user opens an app on a new task and stays there for the entire session, that task's row will not appear in the right pane until the first window change. This is unchanged from the pre-task behavior; it is a known limitation, not a regression.

## Wiring (`core/app.py`)

```python
config = ConfigService(project_root)
tracker, activity_service, time_tracking = create_services(storage, config.detector)
# TimeTrackingService.__init__ gains a `detector: TaskDetector` arg
```

`create_services` is updated to thread the detector through to `TimeTrackingService`. `TaskDetector` itself is exposed as `config.task_detector` for tests and future consumers.

## Error Handling

| Situation | Behavior |
|---|---|
| Window title is `None` or empty | `TaskKey(None, None)` — segment continues with no task |
| No regex match in title | `TaskKey(None, None)` — segment continues with no task |
| Multiple matches in one title | First match wins; documented in `TaskDetector.detect` docstring |
| `trackit.json` missing | Auto-create with `{"task_id_regex": DEFAULT_TASK_ID_REGEX}`; log INFO |
| `trackit.json` has invalid JSON | Log WARNING, use default regex; file untouched |
| `trackit.json` has missing/invalid `task_id_regex` | Log WARNING, use default; file untouched |
| `trackit.json` has invalid regex (compile fails) | Log WARNING, use default; file untouched |
| Task title varies across sightings | First-seen wins; `TaskRepository.upsert` uses `INSERT OR IGNORE` |
| Existing `app_usage` rows from before migration | All have `task_id = NULL`; live in "No task" group |
| User has no active activity | Same as today — `_record_usage` early-returns, no task written |
| Project root not found (running installed) | Fall back to `Path.cwd()` for the config location; still works |

## Testing

No Qt for the new pieces (TaskDetector, ConfigService, repositories). Qt only for the right-pane re-render tests.

- `tests/test_task_detector.py` (≥10 cases)
  - `None` / empty title
  - Plain title, no match
  - "title : ID" format
  - "title.ID" without space
  - "ID: title" (ID at start)
  - Multiple matches (first wins)
  - Title with only the ID, no prefix
  - Title with whitespace-only prefix
  - Title with trailing `:` then ID
  - Custom regex (e.g. lowercase)
- `tests/test_config_service.py` (≥5 cases)
  - Missing file → file created with default
  - Valid file with custom regex → loaded
  - Invalid JSON → default used, file untouched
  - Missing `task_id_regex` key → default used
  - Invalid regex (compile fails) → default used
  - Project root resolution (walk up to `pyproject.toml`)
- `tests/test_app_usage_repository.py` (≥4 cases)
  - Add duration with `task_id=None` (back-compat)
  - Add duration with same `(activity, app, task)` → merges
  - Add duration with same `(activity, app)` but different `task` → separate rows
  - `get_grouped_by_task` returns tasks in correct order
- `tests/test_time_tracking_task.py` (≥5 cases)
  - Flush on window change (no task involved)
  - Flush on task change (same app, new task)
  - Flush on task change (same app, task → None)
  - Flush on task change (same app, None → task)
  - No flush when task is unchanged (same app, same task)
  - `tasks.upsert` is called on first sight of a new task_id, NOT on subsequent sightings
- `tests/test_ui_activity_detail_tasks.py` (≥4 cases)
  - Two tasks + "No task" group render correctly
  - Live segment finds the right `(app, task)` row
  - Task title from `task` table is used (not the current window title)
  - "No task" section is hidden when no such rows exist

## Out of Scope

These are deliberately deferred:

- YouTrack / Jira / GitLab integration for enriching task titles.
- UI to edit or rename tasks manually.
- Per-app regex overrides.
- Manual task assignment (attach a window to a task without a detected ID).
- Backfilling existing `app_usage` rows with detected tasks from `window_title`.
- Hiding or collapsing the "No task" group via a toggle.
- Config UI in a settings dialog.
- Task deletion (currently, `ON DELETE SET NULL` on the FK means deleting a task zeros out the rows; v1 has no delete-task UI).
- A separate "Tasks" top-level pane.
- Exporting task data (CSV, JSON).
- Renaming a task in the right pane.
