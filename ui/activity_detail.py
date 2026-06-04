import logging

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.activity import Activity
from models.app_usage import AppUsage
from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService
from ui.format import format_duration

logger = logging.getLogger(__name__)

TASKS_GROUP_LABEL = "Tasks"
NO_TASK_GROUP_LABEL = "No task"
TASK_TITLE_SEPARATOR = " — "


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

        self._tree = QTreeWidget()
        self._tree.setColumnCount(1)
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet("font-size: 14px;")
        self._tree.setRootIsDecorated(False)
        layout.addWidget(self._tree)

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
        self._tree.clear()
        if self._current_activity_id is None:
            return

        groups = self._storage.app_usage.get_grouped_by_task(self._current_activity_id)
        active_activity = self._activity_service.get_active_activity()
        current_app: str | None = None
        current_task: str | None = None
        if self._window_tracker is not None and self._window_tracker.current_window is not None:
            current_app = self._window_tracker.current_window.app_name
        if self._time_tracking is not None:
            current_task = self._time_tracking.current_task_id

        with_task_groups = [g for g in groups if g.task_id is not None]
        no_task_groups = [g for g in groups if g.task_id is None]

        if with_task_groups:
            tasks_root = QTreeWidgetItem([TASKS_GROUP_LABEL])
            self._tree.addTopLevelItem(tasks_root)
            for group in with_task_groups:
                group_total = sum(a.duration_seconds for a in group.apps)
                title_part = (
                    f" {group.task_title}" if group.task_title else ""
                )
                task_label = (
                    f"{group.task_id}{title_part} {TASK_TITLE_SEPARATOR} "
                    f"{format_duration(group_total)}"
                )
                task_item = QTreeWidgetItem([task_label])
                tasks_root.addChild(task_item)
                for usage in group.apps:
                    is_current = self._is_current(
                        usage, active_activity, current_app, current_task
                    )
                    duration = usage.duration_seconds
                    if is_current and self._time_tracking is not None:
                        duration += self._time_tracking.current_segment_seconds
                    app_label = f"{usage.app_name}  —  {format_duration(duration)}"
                    app_item = QTreeWidgetItem([app_label])
                    if is_current:
                        app_item.setForeground(0, QColor("#c0a000"))
                    task_item.addChild(app_item)
            tasks_root.setExpanded(True)

        if no_task_groups:
            no_task_root = QTreeWidgetItem([NO_TASK_GROUP_LABEL])
            self._tree.addTopLevelItem(no_task_root)
            for group in no_task_groups:
                for usage in group.apps:
                    is_current = self._is_current(
                        usage, active_activity, current_app, current_task
                    )
                    duration = usage.duration_seconds
                    if is_current and self._time_tracking is not None:
                        duration += self._time_tracking.current_segment_seconds
                    app_label = f"{usage.app_name}  —  {format_duration(duration)}"
                    app_item = QTreeWidgetItem([app_label])
                    if is_current:
                        app_item.setForeground(0, QColor("#c0a000"))
                    no_task_root.addChild(app_item)
            no_task_root.setExpanded(True)

    def _is_current(
        self,
        usage: AppUsage,
        active_activity: Activity | None,
        current_app: str | None,
        current_task: str | None,
    ) -> bool:
        return (
            active_activity is not None
            and active_activity.id == self._current_activity_id
            and current_app == usage.app_name
            and current_task == usage.task_id
        )

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
            self._tree.clear()
