import json
import logging
import re
from pathlib import Path

from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "trackit.json"

DEFAULT_CONFIG: dict[str, str] = {
    "task_id_regex": DEFAULT_TASK_ID_REGEX,
}


def find_project_root(start: Path) -> Path:
    """Walk up from `start` looking for pyproject.toml. Fall back to cwd if not found."""
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


class ConfigService:
    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._config_path = project_root / CONFIG_FILENAME
        self._task_id_regex: re.Pattern[str] = re.compile(DEFAULT_TASK_ID_REGEX)
        self._load()

    def _load(self) -> None:
        if not self._config_path.exists():
            try:
                self._config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
                logger.info("Created default config at %s", self._config_path)
            except OSError as exc:
                logger.warning(
                    "Failed to create config at %s: %s — using default regex",
                    self._config_path, exc,
                )
            return

        try:
            data = json.loads(self._config_path.read_text())
        except json.JSONDecodeError as exc:
            logger.warning(
                "Invalid JSON in %s: %s — using default regex",
                self._config_path, exc,
            )
            return

        if not isinstance(data, dict):
            logger.warning(
                "Config at %s is not an object — using default regex", self._config_path,
            )
            return

        pattern = data.get("task_id_regex")
        if not isinstance(pattern, str) or not pattern:
            logger.warning(
                "Missing/invalid task_id_regex in %s — using default", self._config_path,
            )
            return

        try:
            self._task_id_regex = re.compile(pattern)
            logger.info("Loaded task_id_regex from %s: %s", self._config_path, pattern)
        except re.error as exc:
            logger.warning(
                "Invalid regex in %s: %s — using default", self._config_path, exc,
            )

    @property
    def task_detector(self) -> TaskDetector:
        return TaskDetector(self._task_id_regex)
