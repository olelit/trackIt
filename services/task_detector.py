import logging
import re

from models.task_key import TaskKey

logger = logging.getLogger(__name__)

DEFAULT_TASK_ID_REGEX = r"\b([A-Z][A-Z0-9]+-\d+)\b"

_STRIP_CHARS = ": \t-"


class TaskDetector:
    """Extracts a task ID and descriptive title from a window title.

    The detector is stateless and side-effect-free. Construct one per app
    session via ConfigService and share it across services.
    """

    def __init__(self, regex: re.Pattern[str]) -> None:
        self._regex = regex

    def detect(self, window_title: str | None) -> TaskKey:
        if not window_title:
            return TaskKey(None, None)

        match = self._regex.search(window_title)
        if match is None:
            return TaskKey(None, None)

        task_id = match.group(0)
        prefix = window_title[: match.start()].rstrip(_STRIP_CHARS)
        suffix = window_title[match.end():].lstrip(_STRIP_CHARS)
        if prefix:
            task_title: str | None = prefix
        elif suffix:
            task_title = suffix
        else:
            task_title = None
        return TaskKey(task_id, task_title)
