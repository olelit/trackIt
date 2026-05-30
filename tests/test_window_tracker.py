from models.window_info import WindowInfo
from services.window_tracker import WindowTrackerService


def test_window_tracker_starts_and_stops() -> None:
    tracker = WindowTrackerService()
    assert tracker.is_running is False
    tracker.start()
    tracker.stop()
    assert tracker.is_running is False


def test_window_tracker_emits_signal_on_change() -> None:
    tracker = WindowTrackerService()
    received: list[WindowInfo] = []
    tracker.window_changed.connect(lambda w: received.append(w))

    tracker._on_dbus_window_changed("firefox", "Test Page", 0)
    assert len(received) == 1
    assert received[0].app_name == "firefox"
    assert received[0].window_title == "Test Page"


def test_window_tracker_dedup_same_window() -> None:
    tracker = WindowTrackerService()
    received: list[WindowInfo] = []
    tracker.window_changed.connect(lambda w: received.append(w))

    tracker._on_dbus_window_changed("firefox", "Same Page", 0)
    tracker._on_dbus_window_changed("firefox", "Same Page", 0)
    assert len(received) == 1


def test_window_tracker_emits_on_different_window() -> None:
    tracker = WindowTrackerService()
    received: list[WindowInfo] = []
    tracker.window_changed.connect(lambda w: received.append(w))

    tracker._on_dbus_window_changed("firefox", "Page 1", 0)
    tracker._on_dbus_window_changed("konsole", "Terminal", 0)
    assert len(received) == 2
    assert received[0].app_name == "firefox"
    assert received[1].app_name == "konsole"


def test_window_tracker_current_window() -> None:
    tracker = WindowTrackerService()
    assert tracker.current_window is None

    tracker._on_dbus_window_changed("firefox", "Page", 0)
    assert tracker.current_window is not None
    assert tracker.current_window.app_name == "firefox"
