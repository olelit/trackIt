from dataclasses import dataclass


@dataclass(frozen=True)
class AppInfo:
    pid: int | None
    app_name: str
    window_title: str
    ram_mb: int | None
    argv: tuple[str, ...]
    opened_path: str | None
