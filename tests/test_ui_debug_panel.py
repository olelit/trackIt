import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from models.app_info import AppInfo
from services.app_info_service import AppInfoService
from services.window_tracker import WindowTrackerService
from ui.debug_panel import DebugPanel


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


@pytest.fixture
def service(qapp: QApplication) -> AppInfoService:
    return AppInfoService(WindowTrackerService())


@pytest.fixture
def panel(qapp: QApplication, qtbot: pytest.fixture, service: AppInfoService) -> DebugPanel:  # type: ignore[type-arg]
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
    assert panel._toggle_button.text() == "▼"
    qtbot.mouseClick(panel._toggle_button, Qt.MouseButton.LeftButton)
    assert panel.is_collapsed() is False
    assert panel._toggle_button.text() == "▲"
    qtbot.mouseClick(panel._toggle_button, Qt.MouseButton.LeftButton)
    assert panel.is_collapsed() is True
    assert panel._toggle_button.text() == "▼"


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
