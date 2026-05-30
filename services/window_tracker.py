import logging

from PySide6.QtCore import QObject, QTimer, Signal

from models.window_info import WindowInfo

logger = logging.getLogger(__name__)

POLL_INTERVAL_MS = 1000


class WindowTrackerService(QObject):
    window_changed = Signal(WindowInfo)
    tracking_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running: bool = False
        self._current_window: WindowInfo | None = None
        self._timer: QTimer | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_window(self) -> WindowInfo | None:
        return self._current_window

    def start(self) -> bool:
        if self._running:
            return True

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(POLL_INTERVAL_MS)
        self._running = True
        logger.info("WindowTrackerService started (polling %dms)", POLL_INTERVAL_MS)
        return True

    def stop(self) -> None:
        self._running = False
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        logger.info("WindowTrackerService stopped")

    def _poll(self) -> None:
        from PySide6.QtDBus import QDBusConnection, QDBusInterface

        try:
            conn = QDBusConnection.sessionBus()
            iface = QDBusInterface("org.kde.KWin", "/KWin", "org.kde.KWin", conn)
            if not iface.isValid():
                return
            msg = iface.call("getWindowInfo", "")
            if msg.type() != msg.MessageType.ReplyMessage:
                return
            args = msg.arguments()
            if not args or not isinstance(args[0], dict):
                return
            props: dict[str, object] = args[0]
            if not props:
                return
            app_name = str(props.get("resourceClass", ""))
            window_title = str(props.get("caption", ""))
            if app_name or window_title:
                self._on_window_info(app_name, window_title, 0)
        except Exception:
            pass

    def _on_window_info(self, app_name: str, window_title: str, pid: int) -> None:
        if not app_name and not window_title:
            return
        window_info = WindowInfo(
            app_name=app_name or "unknown",
            window_title=window_title or "unknown",
            pid=pid if pid > 0 else None,
        )
        if self._current_window is not None and (
            self._current_window.app_name == window_info.app_name
            and self._current_window.window_title == window_info.window_title
        ):
            return
        self._current_window = window_info
        self.window_changed.emit(window_info)
