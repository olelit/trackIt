import sqlite3
import time
import logging
from typing import Optional
from models.activity import Activity
from models.app_usage import AppUsage

logger = logging.getLogger(__name__)


class ActivityRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, activity: Activity) -> Activity:
        cursor = self._conn.execute(
            "INSERT INTO activity (name, icon_path, is_active, total_duration_seconds) VALUES (?, ?, ?, ?)",
            (activity.name, activity.icon_path, int(activity.is_active), activity.total_duration_seconds),
        )
        self._conn.commit()
        activity.id = cursor.lastrowid or 0
        return activity

    def get_all(self) -> list[Activity]:
        rows = self._conn.execute(
            "SELECT id, name, icon_path, is_active, total_duration_seconds FROM activity ORDER BY id"
        ).fetchall()
        return [Activity(id=r[0], name=r[1], icon_path=r[2], is_active=bool(r[3]), total_duration_seconds=r[4]) for r in rows]

    def get_by_id(self, activity_id: int) -> Optional[Activity]:
        row = self._conn.execute(
            "SELECT id, name, icon_path, is_active, total_duration_seconds FROM activity WHERE id = ?",
            (activity_id,),
        ).fetchone()
        if row is None:
            return None
        return Activity(id=row[0], name=row[1], icon_path=row[2], is_active=bool(row[3]), total_duration_seconds=row[4])

    def get_active(self) -> Optional[Activity]:
        row = self._conn.execute(
            "SELECT id, name, icon_path, is_active, total_duration_seconds FROM activity WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Activity(id=row[0], name=row[1], icon_path=row[2], is_active=bool(row[3]), total_duration_seconds=row[4])

    def set_all_inactive(self) -> None:
        self._conn.execute("UPDATE activity SET is_active = 0")
        self._conn.commit()

    def update(self, activity: Activity) -> None:
        self._conn.execute(
            "UPDATE activity SET name=?, icon_path=?, is_active=?, total_duration_seconds=? WHERE id=?",
            (activity.name, activity.icon_path, int(activity.is_active), activity.total_duration_seconds, activity.id),
        )
        self._conn.commit()

    def delete(self, activity_id: int) -> None:
        self._conn.execute("DELETE FROM activity WHERE id = ?", (activity_id,))
        self._conn.commit()


class AppUsageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, usage: AppUsage) -> AppUsage:
        now = time.time()
        row = self._conn.execute(
            "SELECT id, duration_seconds FROM app_usage WHERE activity_id=? AND app_name=?",
            (usage.activity_id, usage.app_name),
        ).fetchone()

        if row is not None:
            self._conn.execute(
                "UPDATE app_usage SET duration_seconds=?, window_title=?, last_seen_ts=? WHERE id=?",
                (usage.duration_seconds, usage.window_title, now, row[0]),
            )
            self._conn.commit()
            usage.id = row[0]
            usage.last_seen_ts = now
            return usage
        else:
            cursor = self._conn.execute(
                "INSERT INTO app_usage (activity_id, app_name, window_title, duration_seconds, last_seen_ts) VALUES (?, ?, ?, ?, ?)",
                (usage.activity_id, usage.app_name, usage.window_title, usage.duration_seconds, now),
            )
            self._conn.commit()
            usage.id = cursor.lastrowid or 0
            usage.last_seen_ts = now
            return usage

    def get_by_activity(self, activity_id: int) -> list[AppUsage]:
        rows = self._conn.execute(
            "SELECT id, activity_id, app_name, window_title, duration_seconds, last_seen_ts FROM app_usage WHERE activity_id=? ORDER BY duration_seconds DESC",
            (activity_id,),
        ).fetchall()
        return [AppUsage(id=r[0], activity_id=r[1], app_name=r[2], window_title=r[3], duration_seconds=r[4], last_seen_ts=r[5]) for r in rows]

    def add_duration(self, activity_id: int, app_name: str, duration_seconds: int) -> None:
        row = self._conn.execute(
            "SELECT id, duration_seconds FROM app_usage WHERE activity_id=? AND app_name=?",
            (activity_id, app_name),
        ).fetchone()

        now = time.time()
        if row is not None:
            new_duration = row[1] + duration_seconds
            self._conn.execute(
                "UPDATE app_usage SET duration_seconds=?, last_seen_ts=? WHERE id=?",
                (new_duration, now, row[0]),
            )
        else:
            self._conn.execute(
                "INSERT INTO app_usage (activity_id, app_name, duration_seconds, last_seen_ts) VALUES (?, ?, ?, ?)",
                (activity_id, app_name, duration_seconds, now),
            )
        self._conn.commit()
