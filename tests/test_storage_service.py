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
