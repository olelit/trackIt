from dataclasses import dataclass


@dataclass
class WindowInfo:
    app_name: str
    window_title: str
    pid: int | None = None
