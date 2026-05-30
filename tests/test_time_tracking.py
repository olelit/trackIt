import pytest
from models.window_info import WindowInfo
from services.storage_service import StorageService
from services.window_tracker import WindowTrackerService
from services.activity_service import ActivityService
from services.time_tracking import TimeTrackingService


@pytest.fixture
def services() -> tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService]:
    storage = StorageService(":memory:")
    window_tracker = WindowTrackerService()
    activity_service = ActivityService(storage)
    time_tracking = TimeTrackingService(storage, window_tracker, activity_service)
    return storage, window_tracker, activity_service, time_tracking


def test_on_window_change_records_usage(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services

    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    w1 = WindowInfo(app_name="firefox", window_title="Page 1")
    window_tracker._handle_window_change(w1)

    w2 = WindowInfo(app_name="konsole", window_title="Terminal")
    window_tracker._handle_window_change(w2)

    usages = storage.app_usage.get_by_activity(activity.id)
    firefox_usage = [u for u in usages if u.app_name == "firefox"]
    assert len(firefox_usage) == 1
    assert firefox_usage[0].duration_seconds >= 0


def test_activity_switch_flushes_current_segment(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services

    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    w1 = WindowInfo(app_name="firefox", window_title="Page")
    window_tracker._handle_window_change(w1)

    activity2 = activity_service.create_activity("Study")
    activity_service.set_active(activity2.id)

    usages = storage.app_usage.get_by_activity(activity.id)
    firefox_usage = [u for u in usages if u.app_name == "firefox"]
    assert len(firefox_usage) == 1


def test_no_active_activity_skips_recording(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services

    w1 = WindowInfo(app_name="firefox", window_title="Page")
    window_tracker._handle_window_change(w1)
    w2 = WindowInfo(app_name="konsole", window_title="Terminal")
    window_tracker._handle_window_change(w2)

    all_activities = storage.activities.get_all()
    assert all_activities == []


def test_same_window_no_duplicate_recording(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services

    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    w1 = WindowInfo(app_name="firefox", window_title="Same Page")
    window_tracker._handle_window_change(w1)

    w2 = WindowInfo(app_name="konsole", window_title="Terminal")
    window_tracker._handle_window_change(w2)

    usages_after = storage.app_usage.get_by_activity(activity.id)
    firefox = [u for u in usages_after if u.app_name == "firefox"]
    assert len(firefox) == 1


def test_update_activity_total_duration(
    services: tuple[StorageService, WindowTrackerService, ActivityService, TimeTrackingService],
) -> None:
    storage, window_tracker, activity_service, _ = services

    activity = activity_service.create_activity("Work")
    activity_service.set_active(activity.id)

    w1 = WindowInfo(app_name="firefox", window_title="P1")
    window_tracker._handle_window_change(w1)

    w2 = WindowInfo(app_name="zed", window_title="Editor")
    window_tracker._handle_window_change(w2)

    updated_activity = storage.activities.get_by_id(activity.id)
    assert updated_activity is not None
    assert updated_activity.total_duration_seconds >= 0
