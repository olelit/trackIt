from models.activity import Activity
from services.storage_service import StorageService


def test_storage_service_creates_connection() -> None:
    svc = StorageService(":memory:")
    assert svc.conn is not None
    tables = svc.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t[0] for t in tables]
    assert "activity" in table_names
    assert "app_usage" in table_names


def test_storage_service_exposes_repositories() -> None:
    svc = StorageService(":memory:")
    assert svc.activities is not None
    assert svc.app_usage is not None


def test_storage_service_has_foreign_keys_enabled() -> None:
    svc = StorageService(":memory:")
    fk = svc.conn.execute("PRAGMA foreign_keys").fetchone()
    assert fk is not None
    assert fk[0] == 1


def test_storage_service_default_in_memory() -> None:
    svc = StorageService()
    tables = svc.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t[0] for t in tables]
    assert "activity" in table_names


def test_reset_active_clears_state() -> None:
    svc = StorageService(":memory:")
    work = svc.activities.create(Activity(name="Work", is_active=True))
    other = svc.activities.create(Activity(name="Other", is_active=True))
    assert svc.activities.get_active() is not None

    svc.reset_active()

    assert svc.activities.get_active() is None
    reloaded_work = svc.activities.get_by_id(work.id)
    reloaded_other = svc.activities.get_by_id(other.id)
    assert reloaded_work is not None and reloaded_work.is_active is False
    assert reloaded_other is not None and reloaded_other.is_active is False


def test_reset_active_preserves_total_duration() -> None:
    """reset_active only flips is_active; total_duration_seconds and name stay."""
    svc = StorageService(":memory:")
    work = svc.activities.create(
        Activity(name="Work", is_active=True, total_duration_seconds=7200)
    )

    svc.reset_active()

    reloaded = svc.activities.get_by_id(work.id)
    assert reloaded is not None
    assert reloaded.is_active is False
    assert reloaded.name == "Work"
    assert reloaded.total_duration_seconds == 7200
