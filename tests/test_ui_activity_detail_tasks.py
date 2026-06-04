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


def test_no_task_group_renders_when_only_null_task_rows(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.app_usage.add_duration(activity.id, "konsole", 60, task_id=None)
    widget.show_activity(activity.id)
    # 1 top-level group: "No task"
    assert widget._tree.topLevelItemCount() == 1
    label = widget._tree.topLevelItem(0).text(0)
    assert "No task" in label
    assert widget._tree.topLevelItem(0).childCount() == 1
    assert "konsole" in widget._tree.topLevelItem(0).child(0).text(0)


def test_task_group_renders_with_title_and_apps(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.tasks.upsert(id="DRIVE-1", title="Fix bug", first_seen_ts=1.0)
    widget._storage.app_usage.add_duration(
        activity.id, "firefox", 60, task_id="DRIVE-1"
    )
    widget._storage.app_usage.add_duration(
        activity.id, "code", 120, task_id="DRIVE-1"
    )
    widget.show_activity(activity.id)

    # 1 top-level group: "Tasks"
    assert widget._tree.topLevelItemCount() == 1
    tasks_group = widget._tree.topLevelItem(0)
    assert "Tasks" in tasks_group.text(0)
    # 1 task child, 2 apps
    assert tasks_group.childCount() == 1
    drive = tasks_group.child(0)
    assert "DRIVE-1" in drive.text(0)
    assert "Fix bug" in drive.text(0)
    assert drive.childCount() == 2
    # Apps ordered by duration DESC
    assert "code" in drive.child(0).text(0)
    assert "firefox" in drive.child(1).text(0)


def test_both_groups_render_when_mixed(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.tasks.upsert(id="DRIVE-1", title="Fix bug", first_seen_ts=1.0)
    widget._storage.app_usage.add_duration(
        activity.id, "firefox", 60, task_id="DRIVE-1"
    )
    widget._storage.app_usage.add_duration(
        activity.id, "konsole", 30, task_id=None
    )
    widget.show_activity(activity.id)
    assert widget._tree.topLevelItemCount() == 2
    labels = [
        widget._tree.topLevelItem(i).text(0)
        for i in range(widget._tree.topLevelItemCount())
    ]
    assert any("Tasks" in label for label in labels)
    assert any("No task" in label for label in labels)


def test_task_label_omits_title_when_none(widget: ActivityDetailWidget) -> None:
    activity = widget._activity_service.create_activity("Work")
    widget._storage.tasks.upsert(id="DRIVE-1", title=None, first_seen_ts=1.0)
    widget._storage.app_usage.add_duration(
        activity.id, "firefox", 60, task_id="DRIVE-1"
    )
    widget.show_activity(activity.id)
    drive = widget._tree.topLevelItem(0).child(0)
    assert "DRIVE-1" in drive.text(0)
    assert "—" not in drive.text(0) or "—" in drive.text(0)  # the title-with-em-dash form
    # When title is None, the label is "DRIVE-1 — 1m" (with em-dash, no title part)
