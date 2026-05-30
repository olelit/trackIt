from dataclasses import dataclass


@dataclass
class Activity:
    id: int = 0
    name: str = ""
    icon_path: str | None = None
    is_active: bool = False
    total_duration_seconds: int = 0
