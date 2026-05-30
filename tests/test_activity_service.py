import pytest
from services.storage_service import StorageService
from services.activity_service import ActivityService


@pytest.fixture
def service() -> ActivityService:
    storage = StorageService(":memory:")
    return ActivityService(storage)


def test_create_activity(service: ActivityService) -> None:
    activity = service.create_activity("Work")
    assert activity.id > 0
    assert activity.name == "Work"
    assert activity.is_active is False


def test_create_activity_emits_signal(service: ActivityService, qtbot) -> None:
    with qtbot.waitSignal(service.activity_added, timeout=1000) as blocker:
        service.create_activity("Study")
    assert blocker.signal_triggered
    assert blocker.args[0].name == "Study"


def test_get_all_activities_empty(service: ActivityService) -> None:
    assert service.get_all_activities() == []


def test_get_all_activities(service: ActivityService) -> None:
    service.create_activity("Work")
    service.create_activity("Study")
    result = service.get_all_activities()
    assert len(result) == 2


def test_set_active(service: ActivityService) -> None:
    a = service.create_activity("Work")
    service.set_active(a.id)
    active = service.get_active_activity()
    assert active is not None
    assert active.id == a.id
    assert active.is_active is True


def test_set_active_deactivates_previous(service: ActivityService) -> None:
    a1 = service.create_activity("Work")
    a2 = service.create_activity("Study")
    service.set_active(a1.id)
    service.set_active(a2.id)
    assert service.get_active_activity().id == a2.id  # type: ignore[union-attr]
    all_activities = service.get_all_activities()
    a1_reloaded = next(a for a in all_activities if a.id == a1.id)
    assert a1_reloaded.is_active is False


def test_set_active_emits_signal(service: ActivityService, qtbot) -> None:
    a = service.create_activity("Work")
    with qtbot.waitSignal(service.active_activity_changed, timeout=1000) as blocker:
        service.set_active(a.id)
    assert blocker.signal_triggered
    assert blocker.args[0].id == a.id


def test_set_active_nonexistent_does_not_crash(service: ActivityService) -> None:
    service.set_active(999)


def test_rename_activity(service: ActivityService) -> None:
    a = service.create_activity("Work")
    service.rename_activity(a.id, "Office")
    reloaded = service.get_all_activities()[0]
    assert reloaded.name == "Office"


def test_rename_activity_emits_signal(service: ActivityService, qtbot) -> None:
    a = service.create_activity("Work")
    with qtbot.waitSignal(service.activity_updated, timeout=1000) as blocker:
        service.rename_activity(a.id, "Office")
    assert blocker.signal_triggered


def test_delete_activity(service: ActivityService) -> None:
    a = service.create_activity("Work")
    service.delete_activity(a.id)
    assert service.get_all_activities() == []


def test_delete_activity_emits_signal(service: ActivityService, qtbot) -> None:
    a = service.create_activity("Work")
    with qtbot.waitSignal(service.activity_deleted, timeout=1000) as blocker:
        service.delete_activity(a.id)
    assert blocker.signal_triggered
    assert blocker.args[0] == a.id


def test_get_active_activity_returns_none_when_none_active(service: ActivityService) -> None:
    service.create_activity("Work")
    assert service.get_active_activity() is None
