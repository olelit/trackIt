import logging

from PySide6.QtCore import QTimer
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
from ui.format import format_duration

logger = logging.getLogger(__name__)


class ActivityDetailWidget(QWidget):
    def __init__(
        self,
        activity_service: ActivityService,
        storage: StorageService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._activity_service = activity_service
        self._storage = storage
        self._current_activity_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._name_label = QLabel("Select an Activity")
        self._name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self._name_label)

        self._total_time_label = QLabel("")
        layout.addWidget(self._total_time_label)

        self._usage_list = QListWidget()
        layout.addWidget(self._usage_list)

        self._activity_service.activity_updated.connect(self._on_activity_updated)
        self._activity_service.activity_deleted.connect(self._on_activity_deleted)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._periodic_refresh)
        self._refresh_timer.start(30_000)

    def show_activity(self, activity_id: int) -> None:
        activity = self._activity_service._storage.activities.get_by_id(activity_id)
        if activity is None:
            return
        self._current_activity_id = activity_id
        self._update_header(activity)
        self._refresh_usage()

    def _update_header(self, activity: Activity) -> None:
        self._name_label.setText(activity.name)
        self._total_time_label.setText(format_duration(activity.total_duration_seconds))

    def _refresh_usage(self) -> None:
        self._usage_list.clear()
        if self._current_activity_id is None:
            return
        usages = self._storage.app_usage.get_by_activity(self._current_activity_id)
        for usage in usages:
            label = f"{usage.app_name}  —  {format_duration(usage.duration_seconds)}"
            self._usage_list.addItem(QListWidgetItem(label))

    def _periodic_refresh(self) -> None:
        if self._current_activity_id is not None:
            activity = self._storage.activities.get_by_id(self._current_activity_id)
            if activity is not None:
                self._update_header(activity)
                self._refresh_usage()

    def _on_activity_updated(self, activity: Activity) -> None:
        if activity.id == self._current_activity_id:
            self._update_header(activity)
            self._refresh_usage()

    def _on_activity_deleted(self, activity_id: int) -> None:
        if activity_id == self._current_activity_id:
            self._current_activity_id = None
            self._name_label.setText("Select an Activity")
            self._total_time_label.setText("")
            self._usage_list.clear()
