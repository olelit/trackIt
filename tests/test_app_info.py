from models.app_info import AppInfo


def test_app_info_defaults_for_empty_case() -> None:
    info = AppInfo(
        pid=None,
        app_name="",
        window_title="",
        ram_mb=None,
        argv=(),
        opened_path=None,
    )
    assert info.pid is None
    assert info.app_name == ""
    assert info.window_title == ""
    assert info.ram_mb is None
    assert info.argv == ()
    assert info.opened_path is None


def test_app_info_with_values() -> None:
    info = AppInfo(
        pid=1234,
        app_name="firefox",
        window_title="Some Page",
        ram_mb=512,
        argv=("firefox", "--new-window"),
        opened_path="/home/user/proj",
    )
    assert info.pid == 1234
    assert info.app_name == "firefox"
    assert info.window_title == "Some Page"
    assert info.ram_mb == 512
    assert info.argv == ("firefox", "--new-window")
    assert info.opened_path == "/home/user/proj"


def test_app_info_is_frozen() -> None:
    """AppInfo is immutable — accidental mutation would break Qt signal payload semantics."""
    info = AppInfo(
        pid=1, app_name="x", window_title="y", ram_mb=None, argv=(), opened_path=None
    )
    try:
        info.app_name = "z"  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except Exception as e:
        from dataclasses import FrozenInstanceError
        assert isinstance(e, FrozenInstanceError)


def test_app_info_is_hashable() -> None:
    """frozen=True + tuple argv must make the dataclass hashable."""
    info = AppInfo(
        pid=1, app_name="x", window_title="y", ram_mb=None, argv=("a", "b"), opened_path=None
    )
    assert hash(info) is not None
    assert {info, info} == {info}
