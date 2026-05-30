import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal
from models.activity import Activity
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


class ActivityService(QObject):
    activity_added = Signal(Activity)
    activity_updated = Signal(Activity)
    activity_deleted = Signal(int)
    active_activity_changed = Signal(object)  # Activity or None

    def __init__(self, storage: StorageService, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._storage = storage

    def create_activity(self, name: str, icon_path: Optional[str] = None) -> Activity:
        activity = Activity(name=name, icon_path=icon_path)
        activity = self._storage.activities.create(activity)
        logger.info("Created activity: id=%d name=%s", activity.id, activity.name)
        self.activity_added.emit(activity)
        return activity

    def set_active(self, activity_id: int) -> None:
        activity = self._storage.activities.get_by_id(activity_id)
        if activity is None:
            logger.warning("set_active: activity %d not found", activity_id)
            return
        self._storage.activities.set_all_inactive()
        activity.is_active = True
        self._storage.activities.update(activity)
        logger.info("Activated activity: id=%d name=%s", activity.id, activity.name)
        self.active_activity_changed.emit(activity)

    def get_active_activity(self) -> Optional[Activity]:
        return self._storage.activities.get_active()

    def get_all_activities(self) -> list[Activity]:
        return self._storage.activities.get_all()

    def rename_activity(self, activity_id: int, new_name: str) -> None:
        activity = self._storage.activities.get_by_id(activity_id)
        if activity is None:
            logger.warning("rename_activity: activity %d not found", activity_id)
            return
        activity.name = new_name
        self._storage.activities.update(activity)
        self.activity_updated.emit(activity)

    def delete_activity(self, activity_id: int) -> None:
        self._storage.activities.delete(activity_id)
        logger.info("Deleted activity: id=%d", activity_id)
        self.activity_deleted.emit(activity_id)
