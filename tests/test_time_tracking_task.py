import re

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
