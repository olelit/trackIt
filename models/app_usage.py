from dataclasses import dataclass


@dataclass
class AppUsage:
    id: int = 0
    activity_id: int = 0
    app_name: str = ""
    window_title: str | None = None
    duration_seconds: int = 0
    last_seen_ts: float = 0.0
