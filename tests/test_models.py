from models.activity import Activity
from models.window_info import WindowInfo
from models.app_usage import AppUsage


def test_activity_defaults() -> None:
    a = Activity()
    assert a.id == 0
    assert a.name == ""
    assert a.icon_path is None
    assert a.is_active is False
    assert a.total_duration_seconds == 0


def test_activity_with_values() -> None:
    a = Activity(id=1, name="Work", icon_path="/icons/work.png", is_active=True, total_duration_seconds=3600)
    assert a.id == 1
    assert a.name == "Work"
    assert a.icon_path == "/icons/work.png"
    assert a.is_active is True
    assert a.total_duration_seconds == 3600


def test_window_info_defaults() -> None:
    w = WindowInfo(app_name="firefox", window_title="Google - Firefox")
    assert w.app_name == "firefox"
    assert w.window_title == "Google - Firefox"
    assert w.pid is None


def test_window_info_with_pid() -> None:
    w = WindowInfo(app_name="konsole", window_title="~/projects", pid=12345)
    assert w.app_name == "konsole"
    assert w.window_title == "~/projects"
    assert w.pid == 12345


def test_app_usage_defaults() -> None:
    u = AppUsage()
    assert u.id == 0
    assert u.activity_id == 0
    assert u.app_name == ""
    assert u.window_title is None
    assert u.duration_seconds == 0
    assert u.last_seen_ts == 0.0


def test_app_usage_with_values() -> None:
    u = AppUsage(
        id=10, activity_id=1, app_name="firefox",
        window_title="GitHub", duration_seconds=7200, last_seen_ts=1717000000.0
    )
    assert u.id == 10
    assert u.activity_id == 1
    assert u.app_name == "firefox"
    assert u.window_title == "GitHub"
    assert u.duration_seconds == 7200
    assert u.last_seen_ts == 1717000000.0


def test_models_are_dataclasses() -> None:
    """Verify models are dataclasses (field order matters for SQLite row mapping)."""
    from dataclasses import fields
    activity_fields = [f.name for f in fields(Activity)]
    assert activity_fields == ["id", "name", "icon_path", "is_active", "total_duration_seconds"]

    window_fields = [f.name for f in fields(WindowInfo)]
    assert window_fields == ["app_name", "window_title", "pid"]

    usage_fields = [f.name for f in fields(AppUsage)]
    assert usage_fields == ["id", "activity_id", "app_name", "window_title", "duration_seconds", "last_seen_ts"]
