import pytest

from services.activity_service import ActivityService
from services.storage_service import StorageService
from ui.activity_list import ActivityListWidget


@pytest.fixture
def widget(qtbot) -> ActivityListWidget:
    storage = StorageService(":memory:")
    service = ActivityService(storage)
    w = ActivityListWidget(service)
    qtbot.addWidget(w)
    return w


def test_activity_list_starts_empty(widget: ActivityListWidget) -> None:
    assert widget._list_widget.count() == 0


def test_add_button_creates_activity(widget: ActivityListWidget) -> None:
    widget._on_add_clicked()
    assert widget._list_widget.count() == 1


def test_clicking_item_emits_signal(widget: ActivityListWidget, qtbot) -> None:
    activity = widget._activity_service.create_activity("Work")
    assert widget._list_widget.count() == 1

    with qtbot.waitSignal(widget.activity_selected, timeout=1000) as blocker:
        item = widget._list_widget.item(0)
        widget._list_widget.itemClicked.emit(item)

    assert blocker.signal_triggered
    assert blocker.args[0] == activity.id
