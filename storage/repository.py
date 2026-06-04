import logging
import sqlite3
import time

from models.activity import Activity
from models.app_usage import AppUsage
from models.task import Task, TaskGroup

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
        return [
            Activity(id=r[0], name=r[1], icon_path=r[2], is_active=bool(r[3]), total_duration_seconds=r[4])
            for r in rows
        ]

    def get_by_id(self, activity_id: int) -> Activity | None:
        row = self._conn.execute(
            "SELECT id, name, icon_path, is_active, total_duration_seconds FROM activity WHERE id = ?",
            (activity_id,),
        ).fetchone()
        if row is None:
            return None
        return Activity(id=row[0], name=row[1], icon_path=row[2], is_active=bool(row[3]), total_duration_seconds=row[4])

    def get_active(self) -> Activity | None:
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


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, id: str, title: str | None, first_seen_ts: float) -> None:
        """Insert a task row if it does not exist. Never overwrites an existing title (first-seen wins)."""
        self._conn.execute(
            "INSERT OR IGNORE INTO task (id, title, first_seen_ts) VALUES (?, ?, ?)",
            (id, title, first_seen_ts),
        )
        self._conn.commit()

    def get(self, id: str) -> Task | None:
        row = self._conn.execute(
            "SELECT id, title, first_seen_ts FROM task WHERE id = ?", (id,)
        ).fetchone()
        if row is None:
            return None
        return Task(id=row[0], title=row[1], first_seen_ts=row[2])

    def get_all(self) -> list[Task]:
        rows = self._conn.execute(
            "SELECT id, title, first_seen_ts FROM task ORDER BY first_seen_ts"
        ).fetchall()
        return [Task(id=r[0], title=r[1], first_seen_ts=r[2]) for r in rows]


class AppUsageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert(self, usage: AppUsage) -> AppUsage:
        now = time.time()
        row = self._conn.execute(
            "SELECT id, duration_seconds FROM app_usage"
            " WHERE activity_id=? AND app_name=? AND task_id IS ?",
            (usage.activity_id, usage.app_name, usage.task_id),
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
            if usage.task_id is not None:
                self._conn.execute(
                    "INSERT OR IGNORE INTO task (id, title, first_seen_ts) VALUES (?, NULL, ?)",
                    (usage.task_id, now),
                )
            cursor = self._conn.execute(
                "INSERT INTO app_usage"
                " (activity_id, app_name, window_title, duration_seconds, last_seen_ts, task_id)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    usage.activity_id, usage.app_name, usage.window_title,
                    usage.duration_seconds, now, usage.task_id,
                ),
            )
            self._conn.commit()
            usage.id = cursor.lastrowid or 0
            usage.last_seen_ts = now
            return usage

    def get_by_activity(self, activity_id: int) -> list[AppUsage]:
        rows = self._conn.execute(
            "SELECT id, activity_id, app_name, window_title, duration_seconds, last_seen_ts, task_id"
            " FROM app_usage WHERE activity_id=? ORDER BY duration_seconds DESC",
            (activity_id,),
        ).fetchall()
        return [
            AppUsage(
                id=r[0], activity_id=r[1], app_name=r[2], window_title=r[3],
                duration_seconds=r[4], last_seen_ts=r[5], task_id=r[6],
            )
            for r in rows
        ]

    def add_duration(
        self, activity_id: int, app_name: str, duration_seconds: int,
        task_id: str | None = None,
    ) -> None:
        row = self._conn.execute(
            "SELECT id, duration_seconds FROM app_usage"
            " WHERE activity_id=? AND app_name=? AND task_id IS ?",
            (activity_id, app_name, task_id),
        ).fetchone()

        now = time.time()
        if row is not None:
            new_duration = row[1] + duration_seconds
            self._conn.execute(
                "UPDATE app_usage SET duration_seconds=?, last_seen_ts=? WHERE id=?",
                (new_duration, now, row[0]),
            )
        else:
            if task_id is not None:
                self._conn.execute(
                    "INSERT OR IGNORE INTO task (id, title, first_seen_ts) VALUES (?, NULL, ?)",
                    (task_id, now),
                )
            self._conn.execute(
                "INSERT INTO app_usage"
                " (activity_id, app_name, duration_seconds, last_seen_ts, task_id)"
                " VALUES (?, ?, ?, ?, ?)",
                (activity_id, app_name, duration_seconds, now, task_id),
            )
        self._conn.commit()

    def get_grouped_by_task(self, activity_id: int) -> list[TaskGroup]:
        """Return all app_usage rows for the activity, grouped by task_id, with task titles joined in.

        Includes a special group with task_id=None for rows where the task is unassigned.
        """
        rows = self._conn.execute(
            """
            SELECT a.id, a.activity_id, a.app_name, a.window_title,
                   a.duration_seconds, a.last_seen_ts, a.task_id,
                   t.title AS task_title
            FROM app_usage a
            LEFT JOIN task t ON t.id = a.task_id
            WHERE a.activity_id = ?
            ORDER BY a.task_id NULLS LAST, a.duration_seconds DESC
            """,
            (activity_id,),
        ).fetchall()

        groups: dict[str | None, TaskGroup] = {}
        order: list[str | None] = []
        for r in rows:
            usage = AppUsage(
                id=r[0], activity_id=r[1], app_name=r[2], window_title=r[3],
                duration_seconds=r[4], last_seen_ts=r[5], task_id=r[6],
            )
            key = r[6]  # task_id (or None)
            if key not in groups:
                groups[key] = TaskGroup(
                    task_id=key,
                    task_title=r[7],  # may be None
                    apps=(),
                )
                order.append(key)
            groups[key] = TaskGroup(
                task_id=key,
                task_title=r[7],
                apps=groups[key].apps + (usage,),
            )

        return [groups[k] for k in order]
