from services.storage_service import StorageService
from core.app import create_services


def test_create_services_returns_all_three() -> None:
    storage = StorageService(":memory:")
    window_tracker, activity_service, time_tracking = create_services(storage)
    assert window_tracker is not None
    assert activity_service is not None
    assert time_tracking is not None


def test_create_services_wires_signals() -> None:
    storage = StorageService(":memory:")
    window_tracker, activity_service, _ = create_services(storage)
    from models.window_info import WindowInfo
    window_tracker._handle_window_change(WindowInfo(app_name="test", window_title="test"))
    activity_service.create_activity("Test")
