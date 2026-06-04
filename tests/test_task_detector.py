import re

import pytest

from models.task_key import TaskKey
from services.task_detector import DEFAULT_TASK_ID_REGEX, TaskDetector


@pytest.fixture
def detector() -> TaskDetector:
    return TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))


def test_default_regex_is_string() -> None:
    assert isinstance(DEFAULT_TASK_ID_REGEX, str)
    assert DEFAULT_TASK_ID_REGEX


def test_detect_none_title(detector: TaskDetector) -> None:
    assert detector.detect(None) == TaskKey(None, None)


def test_detect_empty_title(detector: TaskDetector) -> None:
    assert detector.detect("") == TaskKey(None, None)


def test_detect_no_match(detector: TaskDetector) -> None:
    assert detector.detect("Just a normal page title") == TaskKey(None, None)


def test_detect_simple_match(detector: TaskDetector) -> None:
    result = detector.detect("DRIVE-1234")
    assert result == TaskKey(task_id="DRIVE-1234", task_title=None)


def test_detect_title_with_id_suffix(detector: TaskDetector) -> None:
    """The canonical example: 'Rewrite-... : DRIVEO-4298'."""
    result = detector.detect("Rewrite-update-price-logic-to-websockets-and-jobs : DRIVEO-4298")
    assert result == TaskKey(
        task_id="DRIVEO-4298",
        task_title="Rewrite-update-price-logic-to-websockets-and-jobs",
    )


def test_detect_title_with_id_prefix(detector: TaskDetector) -> None:
    result = detector.detect("DRIVE-1234: fix login bug")
    assert result.task_id == "DRIVE-1234"
    assert result.task_title == "fix login bug"


def test_detect_multiple_matches_first_wins(detector: TaskDetector) -> None:
    result = detector.detect("DRIVE-1234 is related to DRIVE-5678")
    assert result.task_id == "DRIVE-1234"


def test_detect_strips_trailing_colon_and_space() -> None:
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    result = detector.detect("My title : DRIVE-1234")
    assert result.task_title == "My title"


def test_detect_strips_trailing_dash() -> None:
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    result = detector.detect("My title - DRIVE-1234")
    assert result.task_title == "My title"


def test_detect_keeps_id_when_no_prefix(detector: TaskDetector) -> None:
    result = detector.detect("DRIVE-1234")
    assert result.task_id == "DRIVE-1234"
    assert result.task_title is None


def test_detect_title_only_whitespace_prefix_returns_none_title() -> None:
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    result = detector.detect("  : DRIVE-1234")
    assert result.task_id == "DRIVE-1234"
    assert result.task_title is None


def test_detect_lowercase_id_does_not_match() -> None:
    detector = TaskDetector(re.compile(DEFAULT_TASK_ID_REGEX))
    result = detector.detect("drive-1234 lowercase")
    assert result == TaskKey(None, None)


def test_custom_regex() -> None:
    """A custom regex (e.g. for GitLab-style) should work too."""
    detector = TaskDetector(re.compile(r"#(\d+)"))
    result = detector.detect("Some title #42 extra")
    assert result.task_id == "#42"
    assert result.task_title == "Some title"
