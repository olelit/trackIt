from models.window_info import WindowInfo
from services.window_tracker import WindowTrackerService


def test_window_tracker_starts_and_stops() -> None:
    tracker = WindowTrackerService()
    assert tracker.is_running is False
    tracker.start()
    tracker.stop()
    assert tracker.is_running is False


def test_window_tracker_emits_signal_on_manual_update() -> None:
    """Manually injecting a window change must emit the signal (test hook)."""
    tracker = WindowTrackerService()
    received: list[WindowInfo] = []

    tracker.window_changed.connect(lambda w: received.append(w))

    winfo = WindowInfo(app_name="firefox", window_title="Test Page")
    tracker._handle_window_change(winfo)

    assert len(received) == 1
    assert received[0].app_name == "firefox"
    assert received[0].window_title == "Test Page"


def test_window_tracker_dedup_same_window() -> None:
    """Emitting the same window info twice should NOT emit duplicate signals."""
    tracker = WindowTrackerService()
    received: list[WindowInfo] = []

    tracker.window_changed.connect(lambda w: received.append(w))

    winfo = WindowInfo(app_name="firefox", window_title="Same Page")
    tracker._handle_window_change(winfo)
    tracker._handle_window_change(winfo)

    assert len(received) == 1


def test_window_tracker_emits_on_different_window() -> None:
    """Different window info must emit a new signal."""
    tracker = WindowTrackerService()
    received: list[WindowInfo] = []

    tracker.window_changed.connect(lambda w: received.append(w))

    w1 = WindowInfo(app_name="firefox", window_title="Page 1")
    w2 = WindowInfo(app_name="konsole", window_title="Terminal")
    tracker._handle_window_change(w1)
    tracker._handle_window_change(w2)

    assert len(received) == 2
    assert received[0].app_name == "firefox"
    assert received[1].app_name == "konsole"


def test_window_tracker_current_window() -> None:
    tracker = WindowTrackerService()
    assert tracker.current_window is None

    winfo = WindowInfo(app_name="firefox", window_title="Page")
    tracker._handle_window_change(winfo)
    assert tracker.current_window is not None
    assert tracker.current_window.app_name == "firefox"
