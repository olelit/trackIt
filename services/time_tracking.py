import logging
import time

from PySide6.QtCore import QObject

from models.activity import Activity
from models.task_key import TaskKey
from models.window_info import WindowInfo
from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.task_detector import TaskDetector
from services.window_tracker import WindowTrackerService

logger = logging.getLogger(__name__)


class TimeTrackingService(QObject):
    def __init__(
        self,
        storage: StorageService,
        window_tracker: WindowTrackerService,
        activity_service: ActivityService,
        detector: TaskDetector,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._window_tracker = window_tracker
        self._activity_service = activity_service
        self._detector = detector
        self._segment_start: float = 0.0
        self._current_window: WindowInfo | None = None
        self._current_task: TaskKey | None = None
        self._active_activity: Activity | None = None

        window_tracker.window_changed.connect(self._on_window_changed)
        activity_service.active_activity_changed.connect(self._on_activity_changed)
        logger.info("TimeTrackingService initialized")

    @property
    def current_segment_seconds(self) -> int:
        if self._segment_start <= 0:
            return 0
        return max(0, int(time.time() - self._segment_start))

    @property
    def current_task_id(self) -> str | None:
        return self._current_task.task_id if self._current_task is not None else None

    def _on_window_changed(self, window_info: WindowInfo) -> None:
        now = time.time()
        new_task = self._detector.detect(window_info.window_title)

        if self._current_window is not None and self._segment_start > 0:
            task_changed = new_task != self._current_task
            window_changed = window_info.app_name != self._current_window.app_name
            if task_changed or window_changed:
                duration = int(now - self._segment_start)
                self._record_usage(self._current_window, duration, self._active_activity)

        self._current_window = window_info
        self._current_task = new_task
        self._segment_start = now
        self._record_usage(window_info, 0, self._active_activity)

    def _on_activity_changed(self, activity: Activity | None) -> None:
        if self._current_window is not None and self._segment_start > 0:
            now = time.time()
            duration = int(now - self._segment_start)
            self._record_usage(self._current_window, duration, self._active_activity)
        self._segment_start = time.time()
        self._current_task = None
        self._active_activity = activity

    def _record_usage(
        self, window_info: WindowInfo, duration: int, activity: Activity | None = None
    ) -> None:
        active_activity = activity or self._activity_service.get_active_activity()
        if active_activity is None:
            return

        current_task = self._current_task
        task_id = current_task.task_id if current_task is not None else None
        if current_task is not None and current_task.task_id is not None:
            self._storage.tasks.upsert(
                id=current_task.task_id,
                title=current_task.task_title,
                first_seen_ts=time.time(),
            )

        self._storage.app_usage.add_duration(
            activity_id=active_activity.id,
            app_name=window_info.app_name,
            task_id=task_id,
            duration_seconds=duration,
        )

        active_activity.total_duration_seconds += duration
        self._storage.activities.update(active_activity)

        logger.debug(
            "Recorded %ds for %s (task=%s) under activity %s",
            duration, window_info.app_name, task_id, active_activity.name,
        )
