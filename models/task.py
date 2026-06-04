from dataclasses import dataclass

from models.app_usage import AppUsage


@dataclass(frozen=True)
class Task:
    id: str
    title: str | None = None
    first_seen_ts: float = 0.0


@dataclass(frozen=True)
class TaskGroup:
    task_id: str | None
    task_title: str | None
    apps: tuple[AppUsage, ...] = ()
