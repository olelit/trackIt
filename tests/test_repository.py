import sqlite3
import pytest
from models.activity import Activity
from models.app_usage import AppUsage
from storage.schema import initialize_schema
from storage.repository import ActivityRepository, AppUsageRepository


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    initialize_schema(c)
    return c


class TestActivityRepository:
    def test_create_returns_activity_with_id(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        activity = Activity(name="Work")
        result = repo.create(activity)
        assert result.id > 0
        assert result.name == "Work"
        assert result.is_active is False

    def test_create_persists_to_db(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        repo.create(Activity(name="Work"))
        rows = conn.execute("SELECT * FROM activity").fetchall()
        assert len(rows) == 1

    def test_get_all_returns_empty_list(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        assert repo.get_all() == []

    def test_get_all_returns_activities(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        repo.create(Activity(name="Work"))
        repo.create(Activity(name="Study"))
        result = repo.get_all()
        assert len(result) == 2
        assert result[0].name == "Work"
        assert result[1].name == "Study"

    def test_get_by_id_found(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        created = repo.create(Activity(name="Work"))
        found = repo.get_by_id(created.id)
        assert found is not None
        assert found.name == "Work"

    def test_get_by_id_not_found(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        assert repo.get_by_id(999) is None

    def test_get_active_none(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        assert repo.get_active() is None

    def test_get_active_returns_active(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        a = repo.create(Activity(name="Work"))
        repo.set_all_inactive()
        a.is_active = True
        repo.update(a)
        active = repo.get_active()
        assert active is not None
        assert active.name == "Work"

    def test_set_all_inactive(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        repo.create(Activity(name="Work", is_active=True))
        repo.create(Activity(name="Study", is_active=True))
        repo.set_all_inactive()
        assert repo.get_active() is None

    def test_update_changes_name(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        a = repo.create(Activity(name="Work"))
        a.name = "Office"
        repo.update(a)
        found = repo.get_by_id(a.id)
        assert found is not None
        assert found.name == "Office"

    def test_delete_removes_activity(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        a = repo.create(Activity(name="Work"))
        repo.delete(a.id)
        assert repo.get_by_id(a.id) is None

    def test_delete_cascades_app_usage(self, conn: sqlite3.Connection) -> None:
        repo = ActivityRepository(conn)
        a = repo.create(Activity(name="Work"))
        conn.execute("INSERT INTO app_usage (activity_id, app_name) VALUES (?, ?)", (a.id, "firefox"))
        conn.commit()
        repo.delete(a.id)
        count = conn.execute("SELECT COUNT(*) FROM app_usage WHERE activity_id = ?", (a.id,)).fetchone()[0]
        assert count == 0


class TestAppUsageRepository:
    def test_upsert_inserts_new(self, conn: sqlite3.Connection) -> None:
        a_repo = ActivityRepository(conn)
        activity = a_repo.create(Activity(name="Work"))

        u_repo = AppUsageRepository(conn)
        usage = AppUsage(activity_id=activity.id, app_name="firefox", duration_seconds=600)
        result = u_repo.upsert(usage)
        assert result.id > 0
        assert result.duration_seconds == 600

    def test_upsert_updates_existing(self, conn: sqlite3.Connection) -> None:
        a_repo = ActivityRepository(conn)
        activity = a_repo.create(Activity(name="Work"))

        u_repo = AppUsageRepository(conn)
        existing = AppUsage(activity_id=activity.id, app_name="firefox", duration_seconds=600)
        created = u_repo.upsert(existing)

        updated = AppUsage(id=created.id, activity_id=activity.id, app_name="firefox", duration_seconds=1200)
        result = u_repo.upsert(updated)
        assert result.id == created.id
        assert result.duration_seconds == 1200

    def test_get_by_activity(self, conn: sqlite3.Connection) -> None:
        a_repo = ActivityRepository(conn)
        a1 = a_repo.create(Activity(name="Work"))
        a2 = a_repo.create(Activity(name="Study"))

        u_repo = AppUsageRepository(conn)
        u_repo.upsert(AppUsage(activity_id=a1.id, app_name="firefox", duration_seconds=100))
        u_repo.upsert(AppUsage(activity_id=a1.id, app_name="konsole", duration_seconds=200))
        u_repo.upsert(AppUsage(activity_id=a2.id, app_name="zed", duration_seconds=300))

        a1_usage = u_repo.get_by_activity(a1.id)
        assert len(a1_usage) == 2

        a2_usage = u_repo.get_by_activity(a2.id)
        assert len(a2_usage) == 1

    def test_add_duration_accumulates(self, conn: sqlite3.Connection) -> None:
        a_repo = ActivityRepository(conn)
        activity = a_repo.create(Activity(name="Work"))

        u_repo = AppUsageRepository(conn)
        u_repo.add_duration(activity.id, "firefox", 600)
        u_repo.add_duration(activity.id, "firefox", 300)

        rows = conn.execute(
            "SELECT duration_seconds FROM app_usage WHERE activity_id=? AND app_name=?",
            (activity.id, "firefox")
        ).fetchone()
        assert rows is not None
        assert rows[0] == 900

    def test_add_duration_creates_if_not_exists(self, conn: sqlite3.Connection) -> None:
        a_repo = ActivityRepository(conn)
        activity = a_repo.create(Activity(name="Work"))

        u_repo = AppUsageRepository(conn)
        u_repo.add_duration(activity.id, "newapp", 500)

        rows = conn.execute(
            "SELECT duration_seconds FROM app_usage WHERE activity_id=? AND app_name=?",
            (activity.id, "newapp")
        ).fetchone()
        assert rows is not None
        assert rows[0] == 500
