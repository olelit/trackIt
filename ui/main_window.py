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
