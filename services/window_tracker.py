import logging
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from models.window_info import WindowInfo

logger = logging.getLogger(__name__)

KWIN_SERVICE = "org.kde.KWin"
KWIN_PATH = "/KWin"
KWIN_INTERFACE = "org.kde.KWin"


class WindowTrackerService(QObject):
    window_changed = Signal(WindowInfo)
    tracking_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running: bool = False
        self._current_window: WindowInfo | None = None
        self._dbus_available: bool = False
        self._fallback_timer: QTimer | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_window(self) -> WindowInfo | None:
        return self._current_window

    def start(self) -> bool:
        if self._running:
            return True

        try:
            self._connect_dbus()
            self._running = True
            logger.info("WindowTrackerService started (D-Bus connected)")
            return True
        except Exception as e:
            logger.warning("D-Bus connection failed: %s. Starting fallback polling.", e)
            self.tracking_error.emit(f"D-Bus unavailable: {e}")
            self._start_fallback_polling()
            self._running = True
            return True

    def stop(self) -> None:
        self._running = False
        if self._fallback_timer is not None:
            self._fallback_timer.stop()
            self._fallback_timer = None
        logger.info("WindowTrackerService stopped")

    def _handle_window_change(self, window_info: WindowInfo) -> None:
        if self._current_window is not None and (
            self._current_window.app_name == window_info.app_name
            and self._current_window.window_title == window_info.window_title
        ):
            return

        self._current_window = window_info
        self.window_changed.emit(window_info)

    def _connect_dbus(self) -> None:
        from dasbus.connection import SessionMessageBus  # type: ignore[import-untyped]

        bus = SessionMessageBus()
        proxy: Any = bus.get_proxy(KWIN_SERVICE, KWIN_PATH)

        try:
            current_window_id = proxy.ActiveWindow
            if current_window_id:
                window_info = self._fetch_window_info(proxy, current_window_id)
                if window_info:
                    self._current_window = window_info

            proxy.PropertiesChanged.connect(self._on_kwin_properties_changed)
            self._dbus_available = True
        except AttributeError as e:
            raise RuntimeError(
                f"org.kde.KWin D-Bus interface not found at {KWIN_PATH}"
            ) from e

    def _on_kwin_properties_changed(
        self, interface_name: str, changed_props: dict[str, object], invalidated: list[str]
    ) -> None:
        if interface_name != KWIN_INTERFACE:
            return
        if "ActiveWindow" not in changed_props or "ActiveWindow" in invalidated:
            return

        window_id = changed_props["ActiveWindow"]
        if not window_id:
            return

        from dasbus.connection import SessionMessageBus
        bus = SessionMessageBus()
        proxy: Any = bus.get_proxy(KWIN_SERVICE, KWIN_PATH)
        window_info = self._fetch_window_info(proxy, str(window_id))
        if window_info:
            self._handle_window_change(window_info)

    def _fetch_window_info(self, kwin_proxy: Any, window_id: str) -> WindowInfo | None:
        try:
            app_name = kwin_proxy.getWindowInfo(window_id, "resourceClass")
            window_title = kwin_proxy.getWindowInfo(window_id, "caption")
            pid = kwin_proxy.getWindowInfo(window_id, "pid")
            return WindowInfo(
                app_name=app_name or "unknown",
                window_title=window_title or "unknown",
                pid=pid if pid else None,
            )
        except Exception as e:
            logger.debug("Failed to fetch window info for %s: %s", window_id, e)
            return None

    def _start_fallback_polling(self) -> None:
        self._fallback_timer = QTimer(self)
        self._fallback_timer.timeout.connect(self._poll_active_window)
        self._fallback_timer.start(1000)
        logger.warning("Fallback polling started (1s interval)")

    def _poll_active_window(self) -> None:
        try:
            from dasbus.connection import SessionMessageBus
            bus = SessionMessageBus()
            proxy: Any = bus.get_proxy(KWIN_SERVICE, KWIN_PATH)
            window_id = proxy.ActiveWindow
            if window_id:
                window_info = self._fetch_window_info(proxy, window_id)
                if window_info:
                    self._handle_window_change(window_info)
        except Exception as e:
            logger.debug("Poll failed: %s", e)
