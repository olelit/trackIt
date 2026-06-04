from dataclasses import dataclass


@dataclass(frozen=True)
class TaskKey:
    task_id: str | None = None
    task_title: str | None = None
