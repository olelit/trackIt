import sqlite3
import logging
from storage.schema import initialize_schema
from storage.repository import ActivityRepository, AppUsageRepository

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        initialize_schema(self.conn)
        self.activities = ActivityRepository(self.conn)
        self.app_usage = AppUsageRepository(self.conn)
        logger.info("StorageService initialized (db=%s)", db_path)
