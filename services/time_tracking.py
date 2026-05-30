import time
import logging
from typing import Optional
from PySide6.QtCore import QObject
from models.activity import Activity
from models.window_info import WindowInfo
from services.storage_service import StorageService
from services.window_tracker import WindowTrackerService
from services.activity_service import ActivityService

logger = logging.getLogger(__name__)


class TimeTrackingService(QObject):
    def __init__(
        self,
        storage: StorageService,
        window_tracker: WindowTrackerService,
        activity_service: ActivityService,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._storage = storage
        self._window_tracker = window_tracker
        self._activity_service = activity_service
        self._segment_start: float = 0.0
        self._current_window: Optional[WindowInfo] = None
        self._active_activity: Optional[Activity] = None

        window_tracker.window_changed.connect(self._on_window_changed)
        activity_service.active_activity_changed.connect(self._on_activity_changed)
        logger.info("TimeTrackingService initialized")

    def _on_window_changed(self, window_info: WindowInfo) -> None:
        now = time.time()

        if self._current_window is not None and self._segment_start > 0:
            duration = int(now - self._segment_start)
            self._record_usage(self._current_window, duration, self._active_activity)

        self._current_window = window_info
        self._segment_start = now

    def _on_activity_changed(self, activity: Optional[Activity]) -> None:
        if self._current_window is not None and self._segment_start > 0:
            now = time.time()
            duration = int(now - self._segment_start)
            self._record_usage(self._current_window, duration, self._active_activity)
        self._segment_start = time.time()
        self._active_activity = activity

    def _record_usage(
        self, window_info: WindowInfo, duration: int, activity: Optional[Activity] = None
    ) -> None:
        active_activity = activity or self._activity_service.get_active_activity()
        if active_activity is None:
            return

        self._storage.app_usage.add_duration(
            activity_id=active_activity.id,
            app_name=window_info.app_name,
            duration_seconds=duration,
        )

        active_activity.total_duration_seconds += duration
        self._storage.activities.update(active_activity)

        logger.debug(
            "Recorded %ds for %s under activity %s",
            duration, window_info.app_name, active_activity.name,
        )
