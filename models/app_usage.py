from dataclasses import dataclass
from typing import Optional


@dataclass
class AppUsage:
    id: int = 0
    activity_id: int = 0
    app_name: str = ""
    window_title: Optional[str] = None
    duration_seconds: int = 0
    last_seen_ts: float = 0.0
