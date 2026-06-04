import os
import tempfile

import pytest
from PySide6.QtCore import QCoreApplication

from models.window_info import WindowInfo
from services.app_info_service import AppInfoService
from services.window_tracker import WindowTrackerService

# ---------- _detect_opened_path ----------


def test_heuristic_finds_existing_directory(tmp_path: pytest.TempPathFactory) -> None:  # type: ignore[type-arg]
    """argv = ("code", "<existing dir>") → returns that dir."""
    target = tmp_path / "myproject"
    target.mkdir()
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    result = svc._detect_opened_path(("code", str(target)))
    assert result == str(target)


def test_heuristic_returns_none_for_no_path_args() -> None:
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    result = svc._detect_opened_path(("firefox", "--new-window"))
    assert result is None


def test_heuristic_returns_none_when_path_does_not_exist() -> None:
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    result = svc._detect_opened_path(("code", "/nonexistent/path/abc123"))
    assert result is None


def test_heuristic_skips_flags_starting_with_dashes() -> None:
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    # /tmp is guaranteed to exist on Linux
    result = svc._detect_opened_path(("code", "--wait", "/tmp"))
    assert result == "/tmp"


def test_heuristic_picks_last_path_in_argv(tmp_path: pytest.TempPathFactory) -> None:  # type: ignore[type-arg]
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    result = svc._detect_opened_path(("code", str(a), str(b)))
    assert result == str(b)


def test_heuristic_expands_tilde(monkeypatch: pytest.MonkeyPatch) -> None:
    """A path starting with ~ should be expanded; we use a temp dir as fake HOME."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setenv("HOME", td)
        proj = os.path.join(td, "project")
        os.mkdir(proj)
        svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
        result = svc._detect_opened_path(("code", "~/project"))
        assert result == proj


# ---------- _read_ram_mb ----------


def test_read_ram_returns_none_for_none_pid() -> None:
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    assert svc._read_ram_mb(None) is None


def test_read_ram_returns_mb_for_valid_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """5 MB = 5 * 1024 * 1024 bytes → 5 MB."""
    import psutil

    class FakeMemoryInfo:
        rss = 5 * 1024 * 1024

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def memory_info(self) -> FakeMemoryInfo:
            return FakeMemoryInfo()

    monkeypatch.setattr(psutil, "Process", FakeProcess)
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    assert svc._read_ram_mb(1234) == 5


def test_read_ram_returns_none_for_dead_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    import psutil

    def fake_process(pid: int) -> None:
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", fake_process)
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    assert svc._read_ram_mb(9999) is None


# ---------- _read_argv ----------


def test_read_argv_returns_empty_for_none_pid() -> None:
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    assert svc._read_argv(None) == ()


def test_read_argv_parses_current_process() -> None:
    """The current Python process's /proc/self/cmdline is always readable in tests."""
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    argv = svc._read_argv(os.getpid())
    assert isinstance(argv, tuple)
    assert len(argv) >= 1
    # The first token is the python executable
    assert "python" in argv[0].lower()


def test_read_argv_returns_empty_for_dead_pid() -> None:
    """A PID that almost certainly doesn't exist returns ().

    PID 0 is a special kernel PID on Linux — reading /proc/0/cmdline fails
    with permission denied. We treat any OSError as empty argv.
    """
    svc = AppInfoService.__new__(AppInfoService)  # type: ignore[call-arg]
    assert svc._read_argv(0) == ()


# ---------- orchestrator (needs QApplication) ----------


@pytest.fixture
def qapp() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def tracker(qapp: QCoreApplication) -> WindowTrackerService:
    return WindowTrackerService()


@pytest.fixture
def service(qapp: QCoreApplication, tracker: WindowTrackerService) -> AppInfoService:
    return AppInfoService(tracker)


def test_builds_info_from_window_info(service: AppInfoService) -> None:
    winfo = WindowInfo(
        app_name="firefox",
        window_title="Some Page",
        pid=os.getpid(),
    )
    service._on_window_changed(winfo)
    info = service.current_info
    assert info is not None
    assert info.app_name == "firefox"
    assert info.window_title == "Some Page"
    assert info.pid == os.getpid()
    # RAM and argv are populated from psutil/proc for the current python process
    assert info.ram_mb is not None and info.ram_mb >= 1
    assert len(info.argv) >= 1


def test_handles_unknown_pid(service: AppInfoService) -> None:
    """A WindowInfo with pid=None must not crash; fields are None / empty."""
    winfo = WindowInfo(app_name="konsole", window_title="Terminal", pid=None)
    service._on_window_changed(winfo)
    info = service.current_info
    assert info is not None
    assert info.pid is None
    assert info.ram_mb is None
    assert info.argv == ()


def test_emits_info_updated_on_window_change(
    service: AppInfoService, qtbot: pytest.fixture  # type: ignore[type-arg]
) -> None:
    winfo = WindowInfo(app_name="konsole", window_title="Terminal", pid=None)
    with qtbot.waitSignal(service.info_updated, timeout=1000) as blocker:
        service._on_window_changed(winfo)
    assert blocker.signal_triggered
    assert blocker.args[0].app_name == "konsole"


def test_stop_disconnects_timer(service: AppInfoService) -> None:
    service.stop()
    assert not service._ram_timer.isActive()
