# Default Pause on Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure no Activity is active when TrackIt starts up, regardless of what was active in the previous session.

**Architecture:** A thin `StorageService.reset_active()` method wraps the existing `ActivityRepository.set_all_inactive()`. It is called explicitly from `core/app.py:main()` after services are wired and before window tracking starts. No new state, no schema change, no signal.

**Tech Stack:** Python 3.13, PySide6, SQLite (stdlib), pytest, ruff, mypy — same as the rest of the project.

**Working branch:** All work happens in a feature branch. At the end the branch is squash-merged into `main`. See Task 0.

---

### Task 0: Create the feature branch

**Files:**
- (no file changes)

- [ ] **Step 1: Confirm clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean`.

- [ ] **Step 2: Create and switch to the feature branch**

Run:
```bash
git checkout -b feat/default-pause-on-startup
```

Expected output ends with: `Switched to a new branch 'feat/default-pause-on-startup'`

- [ ] **Step 3: Verify the branch**

Run: `git branch --show-current`
Expected: `feat/default-pause-on-startup`

---

### Task 1: `StorageService.reset_active()` with tests

**Files:**
- Modify: `services/storage_service.py`
- Modify: `tests/test_storage_service.py`

- [ ] **Step 1: Read the existing test file to see what is already imported**

Read `tests/test_storage_service.py` and confirm the current imports. We will need `from models.activity import Activity` to construct Activity objects with `is_active=True`.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_storage_service.py`:

```python
def test_reset_active_clears_state() -> None:
    svc = StorageService(":memory:")
    work = svc.activities.create(Activity(name="Work", is_active=True))
    other = svc.activities.create(Activity(name="Other", is_active=True))
    assert svc.activities.get_active() is not None

    svc.reset_active()

    assert svc.activities.get_active() is None
    reloaded_work = svc.activities.get_by_id(work.id)
    reloaded_other = svc.activities.get_by_id(other.id)
    assert reloaded_work is not None and reloaded_work.is_active is False
    assert reloaded_other is not None and reloaded_other.is_active is False


def test_reset_active_preserves_total_duration() -> None:
    """reset_active only flips is_active; total_duration_seconds and name stay."""
    svc = StorageService(":memory:")
    work = svc.activities.create(
        Activity(name="Work", is_active=True, total_duration_seconds=7200)
    )

    svc.reset_active()

    reloaded = svc.activities.get_by_id(work.id)
    assert reloaded is not None
    assert reloaded.is_active is False
    assert reloaded.name == "Work"
    assert reloaded.total_duration_seconds == 7200
```

If `Activity` is not already imported in the test file, add `from models.activity import Activity` to the imports at the top.

- [ ] **Step 3: Run the tests and verify they fail**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_storage_service.py -v`
Expected: FAIL — `AttributeError: 'StorageService' object has no attribute 'reset_active'`.

- [ ] **Step 4: Add `reset_active()` to `StorageService`**

Modify `services/storage_service.py`. After the existing `__init__` method, add:

```python
    def reset_active(self) -> None:
        """Force all activities to inactive. Intended for application startup."""
        self.activities.set_all_inactive()
        logger.info("All activities reset to inactive on startup")
```

The class `StorageService` already imports `logger` at the top of the file (line 7 of the current file). No new imports needed.

- [ ] **Step 5: Run the tests and verify they pass**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_storage_service.py -v`
Expected: PASS for all tests in the file (4 pre-existing + 2 new = 6 total).

- [ ] **Step 6: Run the full test suite to make sure nothing else broke**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -v`
Expected: PASS for all tests.

- [ ] **Step 7: Lint**

Run: `.venv/bin/ruff check services/storage_service.py tests/test_storage_service.py`
Expected: no errors.

- [ ] **Step 8: Typecheck**

Run: `MYPYPATH=. .venv/bin/mypy services/storage_service.py`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add services/storage_service.py tests/test_storage_service.py
git commit -m "feat: StorageService.reset_active() to clear activity flags on startup"
```

---

### Task 2: Call `reset_active()` from `core/app.py` on startup

**Files:**
- Modify: `core/app.py`

- [ ] **Step 1: Read `core/app.py` to find the right insertion point**

Open `core/app.py` and locate the `main()` function (around lines 95-114). The insertion point is inside `main()`, after `window_tracker, activity_service, time_tracking = create_services(storage)` and before `window_tracker.start()`.

- [ ] **Step 2: Add the call to `main()`**

Modify `core/app.py` inside `main()`. After:

```python
    window_tracker, activity_service, time_tracking = create_services(storage)
```

and before:

```python
    _register_dbus_handler(window_tracker)
```

insert:

```python
    storage.reset_active()
```

The full relevant block should look like:

```python
    storage = StorageService(db_path)
    window_tracker, activity_service, time_tracking = create_services(storage)

    storage.reset_active()

    _register_dbus_handler(window_tracker)
```

- [ ] **Step 3: Run the full test suite — nothing should regress**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -v`
Expected: PASS for all tests. (`core/app.py` is not directly exercised by tests, but smoke-imports in `tests/test_app.py` will catch obvious import errors.)

- [ ] **Step 4: Lint**

Run: `.venv/bin/ruff check core/app.py`
Expected: no errors.

- [ ] **Step 5: Typecheck**

Run: `MYPYPATH=. .venv/bin/mypy core/app.py`
Expected: no errors.

- [ ] **Step 6: Smoke-import the bootstrap path**

Run: `MYPYPATH=. .venv/bin/python -c "from core.app import main; print('OK')"`
Expected output: `OK`

- [ ] **Step 7: Commit**

```bash
git add core/app.py
git commit -m "feat: reset active activities on application startup"
```

---

### Task 3: Verify by inspection and merge

**Files:**
- (no file changes; verification + git operations only)

- [ ] **Step 1: Review the diff against `main`**

Run: `git diff main..HEAD --stat`
Expected: only `services/storage_service.py`, `tests/test_storage_service.py`, and `core/app.py` changed.

- [ ] **Step 2: Inspect the full diff**

Run: `git diff main..HEAD`
Expected: a small, focused diff matching the spec. No stray changes, no debug code, no commented-out code.

- [ ] **Step 3: Final test run**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 4: Final lint + typecheck**

Run: `.venv/bin/ruff check . && MYPYPATH=. .venv/bin/mypy`
Expected: no errors.

- [ ] **Step 5: Push the branch and open a merge step (manual)**

The squash-merge into `main` is performed manually by the user. Push the branch and report the URL:

```bash
git push -u origin feat/default-pause-on-startup
```

Report the branch name and the push output to the user. They will perform the squash-merge.

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] Goal: no Activity active on launch — Task 1 (`StorageService.reset_active`), Task 2 (call from `core/app.py`)
- [x] Total duration preserved — `test_reset_active_preserves_total_duration` in Task 1, Step 2
- [x] Activity remains in the list (only `is_active` is touched) — both tests in Task 1, Step 2 cover this implicitly
- [x] New method on `StorageService` (not on `ActivityRepository` directly) — Task 1, Step 4
- [x] Call from `core/app.py` after `create_services` and before `window_tracker.start()` — Task 2, Step 2
- [x] No new schema, no migration — confirmed in spec; plan makes no DDL changes
- [x] One test asserts basic clear-state, second asserts non-destructive contract — Task 1, Step 2

**2. Placeholder scan:** No "TBD", "TODO", "implement later". Every step has a concrete action, code block, or command with expected output.

**3. Type consistency:**
- `StorageService.reset_active(self) -> None` is defined in Task 1 and called as `storage.reset_active()` (no args) in Task 2 — consistent.
- `Activity(name, is_active, total_duration_seconds)` constructor signature matches existing `models/activity.py` dataclass.
- The repository method `set_all_inactive()` is the same one already in `storage/repository.py:50-52`.
- No signal names are introduced, so no risk of mismatch.
