import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
)
from models.activity import Activity
from services.activity_service import ActivityService
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


class ActivityDetailWidget(QWidget):
    def __init__(
        self,
        activity_service: ActivityService,
        storage: StorageService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._activity_service = activity_service
        self._storage = storage
        self._current_activity_id: Optional[int] = None

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

    def show_activity(self, activity_id: int) -> None:
        activity = self._activity_service._storage.activities.get_by_id(activity_id)
        if activity is None:
            return
        self._current_activity_id = activity_id
        self._update_header(activity)
        self._refresh_usage()

    def _update_header(self, activity: Activity) -> None:
        self._name_label.setText(activity.name)
        hours = activity.total_duration_seconds // 3600
        minutes = (activity.total_duration_seconds % 3600) // 60
        self._total_time_label.setText(f"{hours}h {minutes:02d}m")

    def _refresh_usage(self) -> None:
        self._usage_list.clear()
        if self._current_activity_id is None:
            return
        usages = self._storage.app_usage.get_by_activity(self._current_activity_id)
        for usage in usages:
            hours = usage.duration_seconds // 3600
            minutes = (usage.duration_seconds % 3600) // 60
            duration_str = f"{hours}h {minutes:02d}m" if hours > 0 else f"{minutes}m"
            label = f"{usage.app_name}  —  {duration_str}"
            self._usage_list.addItem(QListWidgetItem(label))

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
