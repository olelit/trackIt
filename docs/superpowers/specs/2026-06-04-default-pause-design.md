# Default Pause on Startup — Design

**Date:** 2026-06-04
**Status:** Approved
**Scope:** Feature #1 of 3 (default pause / task detection / debug panel)

## Goal

On application launch, **no Activity is active**. The user must explicitly press ▶ on an Activity to start tracking. Any Activity that was active at the end of the previous session must become inactive on the next launch.

This matches the user's mental model: "I close the app, time tracking stops. When I open it again, nothing is being tracked until I say so."

## Current Behavior (Problem)

`core/app.py:main()` creates `StorageService` and `ActivityService`, then starts `WindowTrackerService` and shows the UI. It does **not** reset `is_active` flags.

If the previous session ended with Activity "Work" in `is_active=1` state (e.g., the user closed the app, KWin restarted, or the process was killed), the new session starts with "Work" still active and begins recording time immediately — often to the user's surprise.

The `is_active` field is a single boolean column on the `activity` table (`storage/schema.py:13`). The repository method `ActivityRepository.set_all_inactive()` already exists (`storage/repository.py:50-52`).

## Changes

### 1. `services/storage_service.py` — new method

Add a thin wrapper on `StorageService`:

```python
def reset_active(self) -> None:
    """Force all activities to inactive. Intended for application startup."""
    self.activities.set_all_inactive()
    logger.info("All activities reset to inactive on startup")
```

Rationale: the call site (`core/app.py`) should not reach into `storage.activities.set_all_inactive()` directly — that exposes the repository layer to the bootstrap layer. A named method on `StorageService` documents intent and keeps the layering clean.

### 2. `core/app.py` — call the reset at startup

In `main()`, after `create_services(storage)` and before `window_tracker.start()`, add one line:

```python
storage.reset_active()
```

`create_services()` builds `ActivityService`, which is a `QObject` — its `active_activity_changed` signal is not connected to anything yet at that point, so no UI will be notified. The flag is simply cleared in the database before window tracking begins. When `TimeTrackingService._on_window_changed` runs, `self._activity_service.get_active_activity()` returns `None` and `_record_usage` early-returns.

No signal is emitted (no `active_activity_changed(None)`) — at this stage nothing is listening, and the UI re-fetches active state through `get_active_activity()` on its own refresh path.

### 3. Test in `tests/test_storage_service.py`

Add one test:

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
    from models.activity import Activity
    svc = StorageService(":memory:")
    work = svc.activities.create(Activity(name="Work", is_active=True, total_duration_seconds=7200))

    svc.reset_active()

    reloaded = svc.activities.get_by_id(work.id)
    assert reloaded is not None
    assert reloaded.is_active is False
    assert reloaded.name == "Work"
    assert reloaded.total_duration_seconds == 7200
```

The first test covers the basic case (multiple active activities, all cleared). The second test documents the contract: only `is_active` is touched.

## Out of Scope (Explicitly)

- Adding a new "Paused" state to the Activity model. The user already has a "Stop" action (the ⏸ button in `ui/activity_list.py:78-85`) — that is the way to pause. "Default pause" means "no one is active until I say so," not "save my last intent for me."
- Auto-resume on next launch.
- Multi-instance handling. TrackIt assumes a single running instance; if two start, both will reset and both will see "no active." That's acceptable.
- Changing the schema (no new column, no new table).
- Migration of existing databases. The schema is unchanged; existing rows with `is_active=1` will simply be flipped to 0 on the next launch.

## Testing Strategy

- Unit test: `test_reset_active_clears_state` (above).
- Manual: launch the app, activate an Activity, close the app, relaunch, verify the activity shows without a ● marker and the activation button is ▶ (not ⏸).

## Risk

Minimal. The method is idempotent, runs once at startup, and only clears a flag. If a future change needs to skip the reset (e.g., a "kiosk mode" preference), it can be added behind a config flag without touching this method.
