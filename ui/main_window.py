import logging
from typing import Optional
from PySide6.QtWidgets import QMainWindow, QSplitter, QWidget, QVBoxLayout
from PySide6.QtCore import Qt
from services.activity_service import ActivityService
from services.window_tracker import WindowTrackerService
from services.storage_service import StorageService
from ui.activity_list import ActivityListWidget

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        activity_service: ActivityService,
        window_tracker: WindowTrackerService,
        storage: StorageService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("TrackIt")
        self.resize(900, 600)

        self._activity_service = activity_service
        self._window_tracker = window_tracker

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._activity_list = ActivityListWidget(activity_service)
        splitter.addWidget(self._activity_list)

        self._right_panel = QWidget()
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        splitter.addWidget(self._right_panel)

        splitter.setSizes([300, 600])
        self.setCentralWidget(splitter)

        logger.info("MainWindow created")
