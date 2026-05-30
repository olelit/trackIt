import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService
from ui.activity_detail import ActivityDetailWidget
from ui.activity_list import ActivityListWidget

logger = logging.getLogger(__name__)


class DebugPanel(QWidget):
    info_updated = Signal()

    def __init__(
        self,
        window_tracker: WindowTrackerService,
        activity_service: ActivityService,
        time_tracking: TimeTrackingService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tracker = window_tracker
        self._activity_service = activity_service
        self._time_tracking = time_tracking

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._window_label = QLabel("Window: ---")
        self._window_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._window_label)

        layout.addStretch()

        self._activity_label = QLabel("Active: none")
        self._activity_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._activity_label)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(1000)

        self._tracker.window_changed.connect(self._refresh)
        self._activity_service.active_activity_changed.connect(self._refresh)

    def _refresh(self) -> None:
        w = self._tracker.current_window
        if w:
            label = f"{w.app_name} — {w.window_title}"
            if len(label) > 70:
                label = label[:67] + "..."
            self._window_label.setText(f"Window: {label}")
        else:
            self._window_label.setText("Window: ---")

        active = self._activity_service.get_active_activity()
        if active:
            self._activity_label.setText(f"Active: {active.name}")
        else:
            self._activity_label.setText("Active: none")


class MainWindow(QMainWindow):
    def __init__(
        self,
        activity_service: ActivityService,
        window_tracker: WindowTrackerService,
        storage: StorageService,
        time_tracking: TimeTrackingService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("TrackIt")
        self.resize(900, 600)

        self._activity_service = activity_service
        self._window_tracker = window_tracker

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._activity_list = ActivityListWidget(activity_service)
        splitter.addWidget(self._activity_list)

        self._activity_detail = ActivityDetailWidget(activity_service, storage, time_tracking)
        splitter.addWidget(self._activity_detail)

        splitter.setSizes([300, 600])
        main_layout.addWidget(splitter)

        self._debug_panel = DebugPanel(window_tracker, activity_service, time_tracking)
        main_layout.addWidget(self._debug_panel)

        self.setCentralWidget(central)

        self._activity_list.activity_selected.connect(self._activity_detail.show_activity)
        self._window_tracker.window_changed.connect(self._on_window_changed)
        self._debug_panel.info_updated.connect(lambda: None)

        logger.info("MainWindow created")

    def _on_window_changed(self, _window_info: object) -> None:
        self._activity_detail._periodic_refresh()
