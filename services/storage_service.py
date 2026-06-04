import logging
import sqlite3

from storage.repository import ActivityRepository, AppUsageRepository, TaskRepository
from storage.schema import initialize_schema

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        initialize_schema(self.conn)
        self.activities = ActivityRepository(self.conn)
        self.app_usage = AppUsageRepository(self.conn)
        self.tasks = TaskRepository(self.conn)
        logger.info("StorageService initialized (db=%s)", db_path)

    def reset_active(self) -> None:
        """Force all activities to inactive. Intended for application startup."""
        self.activities.set_all_inactive()
        logger.info("All activities reset to inactive on startup")
