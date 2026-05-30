from dataclasses import dataclass
from typing import Optional


@dataclass
class WindowInfo:
    app_name: str
    window_title: str
    pid: Optional[int] = None
