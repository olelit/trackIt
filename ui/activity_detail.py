import logging

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.activity import Activity
from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService
from ui.format import format_duration

logger = logging.getLogger(__name__)


class ActivityDetailWidget(QWidget):
    def __init__(
        self,
        activity_service: ActivityService,
        storage: StorageService,
        time_tracking: TimeTrackingService | None = None,
        window_tracker: WindowTrackerService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._activity_service = activity_service
        self._storage = storage
        self._time_tracking = time_tracking
        self._window_tracker = window_tracker
        self._current_activity_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._name_label = QLabel("Select an Activity")
        self._name_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 4px 0;")
        layout.addWidget(self._name_label)

        self._usage_list = QListWidget()
        self._usage_list.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._usage_list)

        self._activity_service.activity_updated.connect(self._on_activity_updated)
        self._activity_service.activity_deleted.connect(self._on_activity_deleted)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._periodic_refresh)
        self._refresh_timer.start(1000)

    def show_activity(self, activity_id: int) -> None:
        activity = self._activity_service._storage.activities.get_by_id(activity_id)
        if activity is None:
            return
        self._current_activity_id = activity_id
        self._update_header(activity)
        self._refresh_usage()

    def _update_header(self, activity: Activity) -> None:
        self._name_label.setText(activity.name)

    def _refresh_usage(self) -> None:
        self._usage_list.clear()
        if self._current_activity_id is None:
            return
        usages = self._storage.app_usage.get_by_activity(self._current_activity_id)
        active_activity = self._activity_service.get_active_activity()
        current_app = None
        if self._window_tracker is not None and self._window_tracker.current_window is not None:
            current_app = self._window_tracker.current_window.app_name

        for usage in usages:
            duration = usage.duration_seconds
            # Add live segment if this app is currently active AND activity is active
            is_current = (
                active_activity is not None
                and active_activity.id == self._current_activity_id
                and current_app == usage.app_name
            )
            if is_current and self._time_tracking is not None:
                duration += self._time_tracking.current_segment_seconds

            label = f"{usage.app_name}  —  {format_duration(duration)}"
            item = QListWidgetItem(label)

            if is_current:
                item.setForeground(QColor("#c0a000"))

            self._usage_list.addItem(item)

    def _periodic_refresh(self) -> None:
        if self._current_activity_id is not None:
            self._refresh_usage()

    def _on_activity_updated(self, activity: Activity) -> None:
        if activity.id == self._current_activity_id:
            self._refresh_usage()

    def _on_activity_deleted(self, activity_id: int) -> None:
        if activity_id == self._current_activity_id:
            self._current_activity_id = None
            self._name_label.setText("Select an Activity")
            self._usage_list.clear()
