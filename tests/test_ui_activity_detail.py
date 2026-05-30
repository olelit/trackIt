import pytest

from services.activity_service import ActivityService
from services.storage_service import StorageService
from ui.activity_detail import ActivityDetailWidget


@pytest.fixture
def widget(qtbot) -> ActivityDetailWidget:
    storage = StorageService(":memory:")
    service = ActivityService(storage)
    w = ActivityDetailWidget(service, storage)
    qtbot.addWidget(w)
    return w


def test_detail_starts_with_placeholder(widget: ActivityDetailWidget) -> None:
    assert widget._name_label.text() == "Select an Activity"
    assert widget._usage_list.count() == 0


def test_show_activity_updates_header(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget.show_activity(activity.id)
    assert "Work" in widget._name_label.text()


def test_show_activity_shows_app_usage(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.app_usage.add_duration(activity.id, "firefox", 3600)
    widget.show_activity(activity.id)
    assert widget._usage_list.count() == 1
    item = widget._usage_list.item(0)
    assert "firefox" in item.text()


def test_delete_activity_clears_detail(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget.show_activity(activity.id)
    widget._activity_service.delete_activity(activity.id)
    assert widget._name_label.text() == "Select an Activity"
