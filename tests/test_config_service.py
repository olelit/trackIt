import json

from services.config_service import (
    CONFIG_FILENAME,
    DEFAULT_CONFIG,
    ConfigService,
    find_project_root,
)
from services.task_detector import DEFAULT_TASK_ID_REGEX


def test_default_config_has_task_id_regex() -> None:
    assert "task_id_regex" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["task_id_regex"] == DEFAULT_TASK_ID_REGEX


def test_config_filename() -> None:
    assert CONFIG_FILENAME == "trackit.json"


def test_find_project_root_with_pyproject(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_walks_up(tmp_path) -> None:
    sub = tmp_path / "a" / "b" / "c"
    sub.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert find_project_root(sub) == tmp_path


def test_find_project_root_falls_back_to_cwd(tmp_path, monkeypatch) -> None:
    """If no pyproject.toml is found, fall back to cwd."""
    monkeypatch.chdir(tmp_path)
    assert find_project_root(tmp_path / "nowhere") == tmp_path


class TestConfigService:
    def test_missing_file_is_created_with_default(self, tmp_path) -> None:
        service = ConfigService(project_root=tmp_path)
        path = tmp_path / CONFIG_FILENAME
        assert path.exists()
        data = json.loads(path.read_text())
        assert data == DEFAULT_CONFIG
        detector = service.task_detector
        assert detector.detect("DRIVE-1234") is not None

    def test_valid_custom_regex_is_loaded(self, tmp_path) -> None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps({"task_id_regex": r"#(\d+)"}))
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("Some title #42")
        assert result.task_id == "42"

    def test_invalid_json_falls_back_to_default(self, tmp_path) -> None:
        path = tmp_path / CONFIG_FILENAME
        path.write_text("not valid json {{{")
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("DRIVE-1234")
        assert result.task_id == "DRIVE-1234"
        # File must NOT be overwritten
        assert path.read_text() == "not valid json {{{"

    def test_missing_task_id_regex_falls_back_to_default(self, tmp_path) -> None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps({"other_key": "value"}))
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("DRIVE-1234")
        assert result.task_id == "DRIVE-1234"

    def test_invalid_regex_falls_back_to_default(self, tmp_path) -> None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps({"task_id_regex": "(unclosed"}))
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("DRIVE-1234")
        assert result.task_id == "DRIVE-1234"

    def test_non_string_regex_falls_back_to_default(self, tmp_path) -> None:
        (tmp_path / CONFIG_FILENAME).write_text(json.dumps({"task_id_regex": 123}))
        service = ConfigService(project_root=tmp_path)
        result = service.task_detector.detect("DRIVE-1234")
        assert result.task_id == "DRIVE-1234"
