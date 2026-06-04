import re

from core.app import create_services
from services.storage_service import StorageService
from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector


def test_create_services_returns_all_three() -> None:
    storage = StorageService(":memory:")
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    window_tracker, activity_service, time_tracking = create_services(storage, detector)
    assert window_tracker is not None
    assert activity_service is not None
    assert time_tracking is not None


def test_create_services_wires_signals() -> None:
    storage = StorageService(":memory:")
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    window_tracker, activity_service, _ = create_services(storage, detector)
    window_tracker._on_window_info("test", "test", 0)
    activity_service.create_activity("Test")
