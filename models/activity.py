from dataclasses import dataclass
from typing import Optional


@dataclass
class Activity:
    id: int = 0
    name: str = ""
    icon_path: Optional[str] = None
    is_active: bool = False
    total_duration_seconds: int = 0
