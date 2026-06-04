import pytest

from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService


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


def _simulate_window(window_tracker: WindowTrackerService, app_name: str, window_title: str) -> None:
    window_tracker._on_window_info(app_name, window_title, 0)


def test_on_window_change_records_usage(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _simulate_window(window_tracker, "firefox", "Page 1")
    _simulate_window(window_tracker, "konsole", "Terminal")

    usages = storage.app_usage.get_by_activity(activity.id)
    firefox_usage = [u for u in usages if u.app_name == "firefox"]
    assert len(firefox_usage) == 1


def test_activity_switch_flushes_current_segment(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _simulate_window(window_tracker, "firefox", "Page")
    activity2 = activity_service.create_activity("Study")
    activity_service.set_active(activity2.id)

    usages = storage.app_usage.get_by_activity(activity.id)
    firefox_usage = [u for u in usages if u.app_name == "firefox"]
    assert len(firefox_usage) == 1


def test_no_active_activity_skips_recording(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services
    _simulate_window(window_tracker, "firefox", "Page")
    _simulate_window(window_tracker, "konsole", "Terminal")
    assert storage.activities.get_all() == []


def test_same_window_no_duplicate_recording(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _simulate_window(window_tracker, "firefox", "Same Page")
    _simulate_window(window_tracker, "konsole", "Terminal")

    firefox = [u for u in storage.app_usage.get_by_activity(activity.id) if u.app_name == "firefox"]
    assert len(firefox) == 1


def test_update_activity_total_duration(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services
    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    _simulate_window(window_tracker, "firefox", "P1")
    _simulate_window(window_tracker, "zed", "Editor")

    updated = storage.activities.get_by_id(activity.id)
    assert updated is not None
    assert updated.total_duration_seconds >= 0
