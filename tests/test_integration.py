from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService


def _simulate_window(wt: WindowTrackerService, app_name: str, title: str) -> None:
    wt._on_dbus_window_changed(app_name, title, 0)


def test_full_tracking_flow() -> None:
    storage = StorageService(":memory:")
    window_tracker = WindowTrackerService()
    activity_service = ActivityService(storage)
    _time_tracking = TimeTrackingService(storage, window_tracker, activity_service)

    work = activity_service.create_activity("Work")
    study = activity_service.create_activity("Study")

    activity_service.set_active(work.id)
    _simulate_window(window_tracker, "firefox", "Docs")
    _simulate_window(window_tracker, "konsole", "Build")

    activity_service.set_active(study.id)
    work_usage = storage.app_usage.get_by_activity(work.id)
    assert len(work_usage) >= 1

    reloaded_work = storage.activities.get_by_id(work.id)
    assert reloaded_work is not None
    assert reloaded_work.total_duration_seconds >= 0


def test_database_persistence() -> None:
    import os
    import tempfile

    from models.activity import Activity
    db_path = os.path.join(tempfile.gettempdir(), "trackit_test.db")

    try:
        storage = StorageService(db_path)
        activity = storage.activities.create(Activity(name="Test"))
        storage.app_usage.add_duration(activity.id, "firefox", 600)
        del storage

        storage2 = StorageService(db_path)
        activities = storage2.activities.get_all()
        assert len(activities) == 1
        assert activities[0].name == "Test"

        usages = storage2.app_usage.get_by_activity(activities[0].id)
        assert len(usages) == 1
        assert usages[0].app_name == "firefox"
        assert usages[0].duration_seconds == 600
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
