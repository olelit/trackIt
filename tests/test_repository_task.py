import sqlite3

import pytest

from storage.repository import AppUsageRepository, TaskRepository
from storage.schema import initialize_schema


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    initialize_schema(c)
    c.execute("INSERT INTO activity (id, name, is_active, total_duration_seconds) VALUES (1, 'Test', 0, 0)")
    c.commit()
    return c


class TestTaskRepository:
    def test_upsert_inserts_new_task(self, conn: sqlite3.Connection) -> None:
        repo = TaskRepository(conn)
        repo.upsert(id="DRIVE-1234", title="Fix bug", first_seen_ts=100.0)
        task = repo.get("DRIVE-1234")
        assert task is not None
        assert task.id == "DRIVE-1234"
        assert task.title == "Fix bug"
        assert task.first_seen_ts == 100.0

    def test_upsert_does_not_overwrite_existing_title(self, conn: sqlite3.Connection) -> None:
        """First-seen title wins. Later upserts with a different title are ignored."""
        repo = TaskRepository(conn)
        repo.upsert(id="DRIVE-1234", title="Original title", first_seen_ts=100.0)
        repo.upsert(id="DRIVE-1234", title="Different title", first_seen_ts=200.0)
        task = repo.get("DRIVE-1234")
        assert task is not None
        assert task.title == "Original title"

    def test_upsert_with_none_title(self, conn: sqlite3.Connection) -> None:
        repo = TaskRepository(conn)
        repo.upsert(id="DRIVE-1234", title=None, first_seen_ts=100.0)
        task = repo.get("DRIVE-1234")
        assert task is not None
        assert task.title is None

    def test_get_missing_task(self, conn: sqlite3.Connection) -> None:
        repo = TaskRepository(conn)
        assert repo.get("MISSING") is None

    def test_get_all_returns_all_tasks(self, conn: sqlite3.Connection) -> None:
        repo = TaskRepository(conn)
        repo.upsert(id="A-1", title="alpha", first_seen_ts=1.0)
        repo.upsert(id="B-2", title="beta", first_seen_ts=2.0)
        tasks = repo.get_all()
        assert len(tasks) == 2
        ids = {t.id for t in tasks}
        assert ids == {"A-1", "B-2"}


class TestAppUsageRepositoryWithTask:
    def test_add_duration_with_task_id_creates_row(self, conn: sqlite3.Connection) -> None:
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)
        rows = conn.execute("SELECT * FROM app_usage").fetchall()
        assert len(rows) == 1
        assert rows[0][2] == "firefox"  # app_name
        assert rows[0][6] == "DRIVE-1"  # task_id

    def test_add_duration_same_app_different_task_creates_separate_rows(
        self, conn: sqlite3.Connection
    ) -> None:
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-2", duration_seconds=30)
        rows = conn.execute("SELECT * FROM app_usage").fetchall()
        assert len(rows) == 2
        task_ids = {r[6] for r in rows}
        assert task_ids == {"DRIVE-1", "DRIVE-2"}

    def test_add_duration_same_app_same_task_merges(self, conn: sqlite3.Connection) -> None:
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=30)
        rows = conn.execute("SELECT * FROM app_usage").fetchall()
        assert len(rows) == 1
        assert rows[0][4] == 90  # duration_seconds

    def test_add_duration_task_id_none_separate_from_task_rows(
        self, conn: sqlite3.Connection
    ) -> None:
        """Rows with task_id=NULL are separate from rows with a specific task_id."""
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id=None, duration_seconds=60)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=30)
        rows = conn.execute("SELECT * FROM app_usage").fetchall()
        assert len(rows) == 2

    def test_get_grouped_by_task_orders_by_total_duration(self, conn: sqlite3.Connection) -> None:
        """Within each task group, apps are ordered by duration_seconds DESC."""
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)
        repo.add_duration(activity_id=1, app_name="code", task_id="DRIVE-1", duration_seconds=300)
        repo.add_duration(activity_id=1, app_name="firefox", task_id=None, duration_seconds=100)

        groups = repo.get_grouped_by_task(1)
        assert len(groups) == 2
        # Group with task_id='DRIVE-1' has apps ordered by duration
        drive = [g for g in groups if g.task_id == "DRIVE-1"][0]
        assert [a.app_name for a in drive.apps] == ["code", "firefox"]
        # 'No task' group
        no_task = [g for g in groups if g.task_id is None][0]
        assert no_task.task_title is None
        assert [a.app_name for a in no_task.apps] == ["firefox"]

    def test_get_grouped_by_task_includes_title_from_task_table(
        self, conn: sqlite3.Connection
    ) -> None:
        repo_task = TaskRepository(conn)
        repo_task.upsert(id="DRIVE-1", title="Fix bug", first_seen_ts=1.0)
        repo_usage = AppUsageRepository(conn)
        repo_usage.add_duration(activity_id=1, app_name="firefox", task_id="DRIVE-1", duration_seconds=60)

        groups = repo_usage.get_grouped_by_task(1)
        drive = [g for g in groups if g.task_id == "DRIVE-1"][0]
        assert drive.task_title == "Fix bug"

    def test_get_grouped_by_task_returns_no_task_group_for_null_rows(
        self, conn: sqlite3.Connection
    ) -> None:
        repo = AppUsageRepository(conn)
        repo.add_duration(activity_id=1, app_name="konsole", task_id=None, duration_seconds=60)
        groups = repo.get_grouped_by_task(1)
        assert len(groups) == 1
        assert groups[0].task_id is None
        assert groups[0].task_title is None

    def test_get_grouped_by_task_empty(self, conn: sqlite3.Connection) -> None:
        repo = AppUsageRepository(conn)
        assert repo.get_grouped_by_task(99) == []
