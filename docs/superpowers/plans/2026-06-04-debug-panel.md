# Debug Panel with App Info Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a toggleable debug panel to TrackIt that shows the current window's app name, title, PID, RAM, argv, and a heuristic-guess at the opened folder path.

**Architecture:** A new `AppInfo` dataclass is the data carrier. `AppInfoService` (QObject) subscribes to `WindowTrackerService.window_changed`, reads RAM via psutil, argv via `/proc/<pid>/cmdline`, and runs a heuristic for `opened_path`. Emits `info_updated(AppInfo)` on window change and on a 1s RAM refresh timer. `DebugPanel` (QWidget) renders the data. No I/O in the widget. `core/app.py` wires the service and passes it to `MainWindow`, which embeds the panel in a vertical splitter below the existing activity area.

**Tech Stack:** Python 3.13, PySide6, psutil (new dep), SQLite (stdlib), pytest, ruff, mypy.

**Working branch:** All work on `feat/debug-panel`. Squash-merged at the end.

---

### Task 0: Create the feature branch

**Files:**
- (no file changes)

- [ ] **Step 1: Confirm clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean`.

- [ ] **Step 2: Create and switch to the feature branch**

Run:
```bash
git checkout -b feat/debug-panel
```

Expected: `Switched to a new branch 'feat/debug-panel'`

- [ ] **Step 3: Verify**

Run: `git branch --show-current`
Expected: `feat/debug-panel`

---

### Task 1: `AppInfo` dataclass + test

**Files:**
- Create: `models/app_info.py`
- Create: `tests/test_app_info.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_info.py`:

```python
from models.app_info import AppInfo


def test_app_info_defaults_for_empty_case() -> None:
    info = AppInfo(
        pid=None,
        app_name="",
        window_title="",
        ram_mb=None,
        argv=(),
        opened_path=None,
    )
    assert info.pid is None
    assert info.app_name == ""
    assert info.window_title == ""
    assert info.ram_mb is None
    assert info.argv == ()
    assert info.opened_path is None


def test_app_info_with_values() -> None:
    info = AppInfo(
        pid=1234,
        app_name="firefox",
        window_title="Some Page",
        ram_mb=512,
        argv=("firefox", "--new-window"),
        opened_path="/home/user/proj",
    )
    assert info.pid == 1234
    assert info.app_name == "firefox"
    assert info.window_title == "Some Page"
    assert info.ram_mb == 512
    assert info.argv == ("firefox", "--new-window")
    assert info.opened_path == "/home/user/proj"


def test_app_info_is_frozen() -> None:
    """AppInfo is immutable — accidental mutation would break Qt signal payload semantics."""
    info = AppInfo(
        pid=1, app_name="x", window_title="y", ram_mb=None, argv=(), opened_path=None
    )
    try:
        info.app_name = "z"  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except Exception as e:
        from dataclasses import FrozenInstanceError
        assert isinstance(e, FrozenInstanceError)


def test_app_info_is_hashable() -> None:
    """frozen=True + tuple argv must make the dataclass hashable."""
    info = AppInfo(
        pid=1, app_name="x", window_title="y", ram_mb=None, argv=("a", "b"), opened_path=None
    )
    assert hash(info) is not None
    assert {info, info} == {info}
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_app_info.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models.app_info'`.

- [ ] **Step 3: Implement `AppInfo`**

Create `models/app_info.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AppInfo:
    pid: int | None
    app_name: str
    window_title: str
    ram_mb: int | None
    argv: tuple[str, ...]
    opened_path: str | None
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_app_info.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check models/app_info.py tests/test_app_info.py
MYPYPATH=. .venv/bin/mypy models/app_info.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add models/app_info.py tests/test_app_info.py
git commit -m "feat: add AppInfo dataclass for debug panel"
```

---

### Task 2: Add `psutil` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Verify psutil is not already installed**

Run: `.venv/bin/python -c "import psutil" 2>&1`
Expected: `ModuleNotFoundError: No module named 'psutil'`

- [ ] **Step 2: Add psutil to `pyproject.toml`**

Modify `pyproject.toml` — change the `dependencies` list from:

```toml
dependencies = [
    "PySide6>=6.8",
    "dasbus>=1.7",
]
```

to:

```toml
dependencies = [
    "PySide6>=6.8",
    "dasbus>=1.7",
    "psutil>=5.9",
]
```

- [ ] **Step 3: Re-install in editable mode**

Run: `.venv/bin/pip install -e . 2>&1 | tail -5`
Expected output ends with: `Successfully installed psutil-...`

- [ ] **Step 4: Verify import works**

Run: `.venv/bin/python -c "import psutil; print(psutil.__version__)"`
Expected: a version string (e.g., `5.9.8`).

- [ ] **Step 5: Run the full test suite (no regressions expected)**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -q 2>&1 | tail -3`
Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add psutil dependency for app info"
```

---

### Task 3: `WindowTrackerService` reads `pid` from KWin

**Files:**
- Modify: `services/window_tracker.py` (function `_poll`)

- [ ] **Step 1: Read current `_poll` to see the exact location for the change**

Read `services/window_tracker.py` around line 86–106. The function currently reads `resourceClass` and `caption` from the props dict. We add `pid`.

- [ ] **Step 2: Modify `_poll` to read `pid`**

In `services/window_tracker.py`, inside `_poll`, change the lines:

```python
        app_name = str(props.get("resourceClass", ""))
        window_title = str(props.get("caption", ""))
        if app_name or window_title:
            self._on_window_info(app_name, window_title, 0)
```

to:

```python
        app_name = str(props.get("resourceClass", ""))
        window_title = str(props.get("caption", ""))
        raw_pid = props.get("pid", 0)
        try:
            pid = int(raw_pid) if raw_pid else 0
        except (TypeError, ValueError):
            pid = 0
        if app_name or window_title:
            self._on_window_info(app_name, window_title, pid)
```

`_on_window_info` already stores `pid if pid > 0 else None` in `WindowInfo.pid` (line ~114). No other changes needed in this file.

- [ ] **Step 3: Run the full test suite**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -q 2>&1 | tail -3`
Expected: all 70 existing tests pass. (`_poll` is hard to unit-test without mocking QDBus, so we rely on the existing integration coverage.)

- [ ] **Step 4: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check services/window_tracker.py
MYPYPATH=. .venv/bin/mypy services/window_tracker.py
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add services/window_tracker.py
git commit -m "feat: WindowTrackerService reads pid from KWin window props"
```

---

### Task 4: `AppInfoService` (RAM, argv, heuristic) + tests

**Files:**
- Create: `services/app_info_service.py`
- Create: `tests/test_app_info_service.py`

This is the largest task. It introduces the service, all its reader methods, the heuristic, the orchestrator, and the signal/timer wiring. Tests cover each method in isolation plus the orchestrator plus signal emission.

- [ ] **Step 1: Write the heuristic test (pure function)**

Create `tests/test_app_info_service.py` with the following initial content. We'll add more tests in subsequent steps; this first test only covers the heuristic.

```python
import os
import tempfile

import pytest
from PySide6.QtCore import QCoreApplication
from models.app_info import AppInfo
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
```

- [ ] **Step 2: Run heuristic tests — they should fail (module not found)**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_app_info_service.py -v 2>&1 | tail -10`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.app_info_service'`.

- [ ] **Step 3: Implement `_detect_opened_path` (and minimal class stub)**

Create `services/app_info_service.py`:

```python
import logging
import os

from PySide6.QtCore import QObject, QTimer, Signal

from models.app_info import AppInfo
from models.window_info import WindowInfo
from services.window_tracker import WindowTrackerService

logger = logging.getLogger(__name__)


class AppInfoService(QObject):
    info_updated = Signal(AppInfo)

    def __init__(
        self,
        window_tracker: WindowTrackerService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tracker = window_tracker
        self._current_info: AppInfo | None = None
        self._ram_timer = QTimer(self)
        self._ram_timer.setInterval(1000)
        self._ram_timer.timeout.connect(self._refresh_ram_only)
        self._ram_timer.start()
        window_tracker.window_changed.connect(self._on_window_changed)
        logger.info("AppInfoService initialized")

    @property
    def current_info(self) -> AppInfo | None:
        return self._current_info

    def stop(self) -> None:
        self._ram_timer.stop()

    def _on_window_changed(self, winfo: WindowInfo) -> None:
        self._current_info = self._build_info(winfo)
        self.info_updated.emit(self._current_info)

    def _refresh_ram_only(self) -> None:
        if self._current_info is None:
            return
        pid = self._current_info.pid
        if pid is None:
            return
        new_ram = self._read_ram_mb(pid)
        if new_ram == self._current_info.ram_mb:
            return
        self._current_info = AppInfo(
            pid=self._current_info.pid,
            app_name=self._current_info.app_name,
            window_title=self._current_info.window_title,
            ram_mb=new_ram,
            argv=self._current_info.argv,
            opened_path=self._current_info.opened_path,
        )
        self.info_updated.emit(self._current_info)

    def _build_info(self, winfo: WindowInfo) -> AppInfo:
        ram_mb = self._read_ram_mb(winfo.pid)
        argv = self._read_argv(winfo.pid)
        opened_path = self._detect_opened_path(argv)
        return AppInfo(
            pid=winfo.pid,
            app_name=winfo.app_name,
            window_title=winfo.window_title,
            ram_mb=ram_mb,
            argv=argv,
            opened_path=opened_path,
        )

    def _read_ram_mb(self, pid: int | None) -> int | None:
        if pid is None:
            return None
        try:
            import psutil
            rss = psutil.Process(pid).memory_info().rss
            return rss // (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError, ImportError):
            return None

    def _read_argv(self, pid: int | None) -> tuple[str, ...]:
        if pid is None:
            return ()
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                raw = f.read().split(b"\x00")
            return tuple(part.decode("utf-8", errors="replace") for part in raw if part)
        except (OSError, FileNotFoundError, ProcessLookupError):
            return ()

    def _detect_opened_path(self, argv: tuple[str, ...]) -> str | None:
        for token in reversed(argv[1:]):
            if not token.startswith(("/", "~")):
                continue
            if token.startswith("--"):
                continue
            expanded = os.path.expanduser(token)
            if os.path.isdir(expanded):
                return expanded
        return None
```

- [ ] **Step 4: Run heuristic tests — they should now pass**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_app_info_service.py -v`
Expected: PASS for the 6 heuristic tests. (The other tests we add later will fail until we add their code, but those tests aren't in the file yet — Step 1 only added heuristic tests.)

- [ ] **Step 5: Add reader-method tests**

Append to `tests/test_app_info_service.py`:

```python
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
```

- [ ] **Step 6: Run reader tests — they should pass**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_app_info_service.py -v`
Expected: PASS for all 12 tests (6 heuristic + 3 RAM + 3 argv).

- [ ] **Step 7: Add orchestrator + signal tests**

Append to `tests/test_app_info_service.py`:

```python
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
```

- [ ] **Step 8: Run the full file — all tests should pass**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_app_info_service.py -v`
Expected: PASS for all 16 tests.

- [ ] **Step 9: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check services/app_info_service.py tests/test_app_info_service.py
MYPYPATH=. .venv/bin/mypy services/app_info_service.py
```

Expected: no errors.

- [ ] **Step 10: Run the full test suite — no regressions**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -q 2>&1 | tail -3`
Expected: all tests pass (70 prior + 16 new = 86).

- [ ] **Step 11: Commit**

```bash
git add services/app_info_service.py tests/test_app_info_service.py
git commit -m "feat: AppInfoService gathers RAM, argv, opened_path from window"
```

---

### Task 5: `DebugPanel` widget + tests

**Files:**
- Create: `ui/debug_panel.py`
- Create: `tests/test_ui_debug_panel.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ui_debug_panel.py`:

```python
import pytest
from PySide6.QtCore import QCoreApplication
from models.app_info import AppInfo
from services.app_info_service import AppInfoService
from services.window_tracker import WindowTrackerService
from ui.debug_panel import DebugPanel


@pytest.fixture
def qapp() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def service(qapp: QCoreApplication) -> AppInfoService:
    return AppInfoService(WindowTrackerService())


@pytest.fixture
def panel(qapp: QCoreApplication, qtbot: pytest.fixture, service: AppInfoService) -> DebugPanel:  # type: ignore[type-arg]
    p = DebugPanel(service)
    qtbot.addWidget(p)
    return p


def test_starts_collapsed(panel: DebugPanel) -> None:
    assert panel.is_collapsed() is True


def test_collapsed_state_shows_summary(panel: DebugPanel) -> None:
    info = AppInfo(
        pid=1234,
        app_name="firefox",
        window_title="Some Page",
        ram_mb=512,
        argv=("firefox",),
        opened_path=None,
    )
    panel._on_info_updated(info)
    summary = panel._summary_label.text()
    assert "firefox" in summary
    assert "Some Page" in summary
    assert "512" in summary


def test_expanded_state_shows_details(panel: DebugPanel) -> None:
    info = AppInfo(
        pid=1234,
        app_name="code",
        window_title="Project",
        ram_mb=128,
        argv=("code", "/tmp"),
        opened_path="/tmp",
    )
    panel.set_collapsed(False)
    panel._on_info_updated(info)
    assert "1234" in panel._pid_label.text()
    assert "/tmp" in panel._argv_label.text()
    assert "/tmp" in panel._opened_label.text()


def test_toggle_button_switches_collapsed_state(
    panel: DebugPanel, qtbot: pytest.fixture  # type: ignore[type-arg]
) -> None:
    assert panel.is_collapsed() is True
    qtbot.mouseClick(panel._toggle_button, 1)  # type: ignore[arg-type]
    assert panel.is_collapsed() is False
    qtbot.mouseClick(panel._toggle_button, 1)  # type: ignore[arg-type]
    assert panel.is_collapsed() is True


def test_handles_empty_info_gracefully(panel: DebugPanel) -> None:
    panel._on_info_updated(None)
    summary = panel._summary_label.text()
    # Em-dash or "none" is acceptable
    assert "—" in summary or "none" in summary.lower()


def test_updates_labels_on_info_signal(panel: DebugPanel) -> None:
    first = AppInfo(pid=1, app_name="a", window_title="x", ram_mb=10, argv=(), opened_path=None)
    second = AppInfo(pid=2, app_name="b", window_title="y", ram_mb=20, argv=(), opened_path=None)
    panel._on_info_updated(first)
    assert "a" in panel._summary_label.text()
    panel._on_info_updated(second)
    assert "b" in panel._summary_label.text()


def test_long_window_title_truncated(panel: DebugPanel) -> None:
    long_title = "x" * 200
    info = AppInfo(
        pid=1, app_name="app", window_title=long_title,
        ram_mb=None, argv=(), opened_path=None,
    )
    panel._on_info_updated(info)
    summary = panel._summary_label.text()
    # The full title must NOT appear, only a truncated form
    assert long_title not in summary
    assert "…" in summary
```

- [ ] **Step 2: Run tests — they should fail (module not found)**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_ui_debug_panel.py -v 2>&1 | tail -10`
Expected: FAIL with `ModuleNotFoundError: No module named 'ui.debug_panel'`.

- [ ] **Step 3: Implement `DebugPanel`**

Create `ui/debug_panel.py`:

```python
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.app_info import AppInfo
from services.app_info_service import AppInfoService

logger = logging.getLogger(__name__)


SUMMARY_TITLE_MAX = 80
ARGV_DISPLAY_MAX = 200


class DebugPanel(QWidget):
    def __init__(
        self,
        app_info_service: AppInfoService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = app_info_service
        self._collapsed = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row: title + collapse toggle
        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 0)
        title = QLabel("Debug")
        title.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self._toggle_button = QPushButton("▼")
        self._toggle_button.setFixedWidth(28)
        self._toggle_button.setStyleSheet("color: #888; font-size: 11px;")
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        header.addWidget(self._toggle_button)
        layout.addLayout(header)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Summary line (always visible)
        self._summary_label = QLabel("Window: — | RAM: —")
        self._summary_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px 8px;")
        self._summary_label.setWordWrap(False)
        self._summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._summary_label)

        # Details (visibility toggled)
        self._details = QWidget()
        details_layout = QVBoxLayout(self._details)
        details_layout.setContentsMargins(8, 4, 8, 4)
        details_layout.setSpacing(2)

        self._pid_label = QLabel("PID: —")
        self._pid_label.setStyleSheet("color: #888; font-size: 11px;")
        self._pid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self._pid_label)

        self._argv_label = QLabel("Argv: —")
        self._argv_label.setStyleSheet("color: #888; font-size: 11px;")
        self._argv_label.setWordWrap(True)
        self._argv_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self._argv_label)

        self._opened_label = QLabel("Opened: —")
        self._opened_label.setStyleSheet("color: #888; font-size: 11px;")
        self._opened_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self._opened_label)

        layout.addWidget(self._details)
        self._details.setVisible(False)

        self._service.info_updated.connect(self._on_info_updated)

        logger.info("DebugPanel created")

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._details.setVisible(not collapsed)
        self._toggle_button.setText("▲" if collapsed else "▼")

    def _on_toggle_clicked(self) -> None:
        self.set_collapsed(not self._collapsed)

    def _on_info_updated(self, info: AppInfo | None) -> None:
        if info is None:
            self._summary_label.setText("Window: — | RAM: —")
            self._pid_label.setText("PID: —")
            self._argv_label.setText("Argv: —")
            self._opened_label.setText("Opened: —")
            return

        title = info.window_title
        if len(title) > SUMMARY_TITLE_MAX:
            title = title[: SUMMARY_TITLE_MAX - 1] + "…"
        ram = f"{info.ram_mb} MB" if info.ram_mb is not None else "—"
        self._summary_label.setText(f"Window: {info.app_name} — {title} | RAM: {ram}")

        pid_text = str(info.pid) if info.pid is not None else "—"
        self._pid_label.setText(f"PID: {pid_text}")

        if info.argv:
            argv_text = " ".join(info.argv)
            if len(argv_text) > ARGV_DISPLAY_MAX:
                argv_text = argv_text[: ARGV_DISPLAY_MAX - 1] + "…"
            self._argv_label.setText(f"Argv: {argv_text}")
        else:
            self._argv_label.setText("Argv: —")

        opened = info.opened_path if info.opened_path is not None else "—"
        self._opened_label.setText(f"Opened: {opened}")
```

- [ ] **Step 4: Run tests — they should pass**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/test_ui_debug_panel.py -v`
Expected: PASS for all 7 tests.

- [ ] **Step 5: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check ui/debug_panel.py tests/test_ui_debug_panel.py
MYPYPATH=. .venv/bin/mypy ui/debug_panel.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add ui/debug_panel.py tests/test_ui_debug_panel.py
git commit -m "feat: DebugPanel widget with toggleable details"
```

---

### Task 6: Wire everything in `core/app.py` and `ui/main_window.py`

**Files:**
- Modify: `core/app.py`
- Modify: `ui/main_window.py`

- [ ] **Step 1: Read current `core/app.py:main` and `ui/main_window.py:__init__`**

Open both files. In `core/app.py` find the `main()` function (around lines 95-114). In `ui/main_window.py` find the `__init__` method (around lines 22-60).

- [ ] **Step 2: Modify `core/app.py` to create `AppInfoService` and pass it to `MainWindow`**

In `core/app.py`, inside `main()`, after the `storage.reset_active()` line, add:

```python
    app_info_service = AppInfoService(window_tracker)
```

Then change the line that creates `MainWindow`:

```python
    window = MainWindow(activity_service, window_tracker, storage, time_tracking)
```

to:

```python
    window = MainWindow(activity_service, window_tracker, storage, time_tracking, app_info_service)
```

After `app.exec()` returns (where `window_tracker.stop()` is called), also add:

```python
    app_info_service.stop()
```

The full relevant block becomes:

```python
    storage = StorageService(db_path)
    window_tracker, activity_service, time_tracking = create_services(storage)

    storage.reset_active()

    app_info_service = AppInfoService(window_tracker)

    _register_dbus_handler(window_tracker)

    from ui.main_window import MainWindow
    window = MainWindow(activity_service, window_tracker, storage, time_tracking, app_info_service)
    window.show()

    window_tracker.start()

    exit_code = app.exec()
    window_tracker.stop()
    app_info_service.stop()
    logger.info("TrackIt exiting (code=%d)", exit_code)
    sys.exit(exit_code)
```

Also add the import at the top of `core/app.py`, in the import block near the other `services` imports:

```python
from services.app_info_service import AppInfoService
```

- [ ] **Step 3: Modify `ui/main_window.py` to accept `app_info_service` and embed the panel**

Replace the entire contents of `ui/main_window.py` with:

```python
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from services.activity_service import ActivityService
from services.app_info_service import AppInfoService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService
from ui.activity_detail import ActivityDetailWidget
from ui.activity_list import ActivityListWidget
from ui.debug_panel import DebugPanel

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        activity_service: ActivityService,
        window_tracker: WindowTrackerService,
        storage: StorageService,
        time_tracking: TimeTrackingService,
        app_info_service: AppInfoService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("TrackIt")
        self.resize(900, 600)

        self._activity_service = activity_service
        self._window_tracker = window_tracker
        self._app_info_service = app_info_service

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Existing horizontal splitter for activity list + detail
        self._activity_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._activity_list = ActivityListWidget(activity_service)
        self._activity_splitter.addWidget(self._activity_list)
        self._activity_detail = ActivityDetailWidget(
            activity_service, storage, time_tracking, window_tracker
        )
        self._activity_splitter.addWidget(self._activity_detail)
        self._activity_splitter.setSizes([300, 600])

        # New vertical splitter to host the debug panel below
        outer_splitter = QSplitter(Qt.Orientation.Vertical)
        outer_splitter.addWidget(self._activity_splitter)
        self._debug_panel = DebugPanel(app_info_service)
        outer_splitter.addWidget(self._debug_panel)
        outer_splitter.setSizes([500, 100])

        main_layout.addWidget(outer_splitter)
        self.setCentralWidget(central)

        self._activity_list.activity_selected.connect(self._activity_detail.show_activity)
        self._window_tracker.window_changed.connect(lambda _: self._activity_detail._periodic_refresh())

        logger.info("MainWindow created")
```

- [ ] **Step 4: Update `tests/test_app.py` to pass the new argument**

Read `tests/test_app.py` first to see its current shape. The test creates services via `create_services(storage)` and may construct `MainWindow` directly. We must pass the new `app_info_service` argument. Open the file and update any call to `MainWindow(...)` to pass an `AppInfoService(WindowTrackerService())` instance.

If `tests/test_app.py` does not construct `MainWindow` directly, no changes are needed. (Run the tests to find out.)

- [ ] **Step 5: Run the full test suite**

Run: `MYPYPATH=. .venv/bin/python -m pytest tests/ -q 2>&1 | tail -5`
Expected: all tests pass. If `tests/test_app.py` fails due to the new arg, fix it as per Step 4.

- [ ] **Step 6: Lint + typecheck**

Run:
```bash
.venv/bin/ruff check .
MYPYPATH=. .venv/bin/mypy
```

Expected: no errors.

- [ ] **Step 7: Smoke-import the bootstrap path**

Run: `MYPYPATH=. .venv/bin/python -c "from core.app import main; print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add core/app.py ui/main_window.py tests/test_app.py
git commit -m "feat: wire AppInfoService and DebugPanel into main window"
```

(If `tests/test_app.py` was not changed, omit it from `git add`.)

---

### Task 7: Verify, push, merge

**Files:**
- (no file changes)

- [ ] **Step 1: Review the diff against `main`**

Run: `git diff main..HEAD --stat`
Expected: 5-7 files changed (`models/app_info.py`, `services/window_tracker.py`, `services/app_info_service.py`, `ui/debug_panel.py`, `ui/main_window.py`, `core/app.py`, `pyproject.toml`, plus test files).

- [ ] **Step 2: Final test + lint + typecheck**

Run:
```bash
MYPYPATH=. .venv/bin/python -m pytest tests/ -q
.venv/bin/ruff check .
MYPYPATH=. .venv/bin/mypy
```

Expected: all green.

- [ ] **Step 3: Push the branch**

```bash
git push -u origin feat/debug-panel
```

Report the URL to the user.

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] AppInfo dataclass → Task 1
- [x] AppInfoService with psutil, /proc, heuristic → Task 4
- [x] WindowTrackerService reads pid → Task 3
- [x] DebugPanel widget, toggleable → Task 5
- [x] Toggleable bottom drawer layout (vertical splitter) → Task 6 (Step 3)
- [x] psutil dependency → Task 2
- [x] Wire in core/app.py and ui/main_window.py → Task 6
- [x] Tests for all of the above → Tasks 1, 4, 5
- [x] RAM and argv are None/empty when PID unknown → Task 4 (Step 5)
- [x] Heuristic skips flags, finds last existing dir → Task 4 (Step 1)
- [x] Long window title and argv truncated for display → Task 5 (Step 3)
- [x] Empty info state shows dashes → Task 5 (Step 1)
- [x] app_info_service.stop() called on shutdown → Task 6 (Step 2)

**2. Placeholder scan:** No "TBD", "TODO", "implement later", or "similar to Task N". Every code step has a complete code block. Every command has expected output.

**3. Type consistency:**
- `AppInfo` field names, types, and order (`pid, app_name, window_title, ram_mb, argv, opened_path`) are identical between spec, Task 1 implementation, Task 4 references, and Task 5 references.
- `AppInfoService.__init__(window_tracker, parent=None)` consistent across all tasks.
- `AppInfoService.info_updated = Signal(AppInfo)` consistent.
- `AppInfoService.current_info` property is a `AppInfo | None`.
- `AppInfoService.stop()` defined in Task 4 and called in Task 6.
- `DebugPanel.__init__(app_info_service, parent=None)` consistent.
- `DebugPanel._on_info_updated(info: AppInfo | None)` signature: accepts None in Task 5 test `test_handles_empty_info_gracefully`. Implementation handles None explicitly.
- `MainWindow.__init__` adds `app_info_service: AppInfoService` as the 5th positional arg in Task 6, consistent with `core/app.py` call site.
- `WindowInfo` already has `pid: int | None`; the `_poll` change in Task 3 just feeds it from props.

**4. Task ordering rationale:** Each task leaves the system in a working state with all tests green. Tasks 1-3 are small foundational pieces (model, dep, existing-class tweak). Task 4 is the bulk of the new logic. Task 5 is the bulk of the new UI. Task 6 wires them in. Task 7 verifies and ships.
