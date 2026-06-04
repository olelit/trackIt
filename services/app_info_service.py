import logging
import os

from PySide6.QtCore import QObject, QTimer, Signal

from models.app_info import AppInfo
from models.window_info import WindowInfo
from services.window_tracker import WindowTrackerService

logger = logging.getLogger(__name__)


class AppInfoService(QObject):
    info_updated = Signal(AppInfo)

    def __init__(
        self,
        window_tracker: WindowTrackerService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tracker = window_tracker
        self._current_info: AppInfo | None = None
        self._ram_timer = QTimer(self)
        self._ram_timer.setInterval(1000)
        self._ram_timer.timeout.connect(self._refresh_ram_only)
        self._ram_timer.start()
        window_tracker.window_changed.connect(self._on_window_changed)
        logger.info("AppInfoService initialized")

    @property
    def current_info(self) -> AppInfo | None:
        return self._current_info

    def stop(self) -> None:
        self._ram_timer.stop()

    def _on_window_changed(self, winfo: WindowInfo) -> None:
        self._current_info = self._build_info(winfo)
        self.info_updated.emit(self._current_info)

    def _refresh_ram_only(self) -> None:
        if self._current_info is None:
            return
        pid = self._current_info.pid
        if pid is None:
            return
        new_ram = self._read_ram_mb(pid)
        if new_ram == self._current_info.ram_mb:
            return
        self._current_info = AppInfo(
            pid=self._current_info.pid,
            app_name=self._current_info.app_name,
            window_title=self._current_info.window_title,
            ram_mb=new_ram,
            argv=self._current_info.argv,
            opened_path=self._current_info.opened_path,
        )
        self.info_updated.emit(self._current_info)

    def _build_info(self, winfo: WindowInfo) -> AppInfo:
        ram_mb = self._read_ram_mb(winfo.pid)
        argv = self._read_argv(winfo.pid)
        opened_path = self._detect_opened_path(argv)
        return AppInfo(
            pid=winfo.pid,
            app_name=winfo.app_name,
            window_title=winfo.window_title,
            ram_mb=ram_mb,
            argv=argv,
            opened_path=opened_path,
        )

    def _read_ram_mb(self, pid: int | None) -> int | None:
        if pid is None:
            return None
        try:
            import psutil  # type: ignore[import-untyped]
            rss = psutil.Process(pid).memory_info().rss
            return int(rss) // (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError, ImportError):
            return None

    def _read_argv(self, pid: int | None) -> tuple[str, ...]:
        if pid is None:
            return ()
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                raw = f.read().split(b"\x00")
            return tuple(part.decode("utf-8", errors="replace") for part in raw if part)
        except (OSError, FileNotFoundError, ProcessLookupError):
            return ()

    def _detect_opened_path(self, argv: tuple[str, ...]) -> str | None:
        for token in reversed(argv[1:]):
            if not token.startswith(("/", "~")):
                continue
            if token.startswith("--"):
                continue
            expanded = os.path.expanduser(token)
            if os.path.isdir(expanded):
                return expanded
        return None
