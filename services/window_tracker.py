import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage, QDBusVirtualObject

from models.window_info import WindowInfo

logger = logging.getLogger(__name__)

KWIN_SERVICE = "org.kde.KWin"
KWIN_SCRIPTING_PATH = "/Scripting"
KWIN_SCRIPTING_IFACE = "org.kde.kwin.Scripting"

TRACKIT_SERVICE = "org.trackit.App"
TRACKIT_PATH = "/org/trackit/App"

SCRIPT_INSTALL_DIR = Path.home() / ".local" / "share" / "kwin" / "scripts" / "trackit"

KWIN_SCRIPT_JS = """\
// TrackIt KWin script — reports active window info via D-Bus
// Installed and loaded automatically by the TrackIt Python app.

function notifyWindow(window) {
    if (!window) return;
    callDBus(
        "org.trackit.App",
        "/org/trackit/App",
        "org.trackit.App",
        "windowChanged",
        window.resourceClass || "",
        window.caption || "",
        window.pid || 0
    );
}

workspace.windowActivated.connect(notifyWindow);

if (workspace.activeWindow) {
    notifyWindow(workspace.activeWindow);
}
"""

KWIN_METADATA_JSON = """\
{
    "KPlugin": {
        "Name": "TrackIt Window Tracker",
        "Description": "Reports active window info for TrackIt app",
        "Icon": "preferences-system-time",
        "EnabledByDefault": true,
        "Version": "1.0"
    },
    "X-Plasma-API": "javascript",
    "X-Plasma-MainScript": "code/main.js"
}
"""


class _DBusHandler(QDBusVirtualObject):
    """Handles D-Bus method calls regardless of interface name."""

    def __init__(self, tracker: "WindowTrackerService") -> None:
        super().__init__()
        self._tracker = tracker

    def handleMessage(self, message: QDBusMessage, connection: QDBusConnection) -> bool:  # noqa: N802
        method = message.member()
        args = message.arguments()
        if method == "windowChanged" and len(args) >= 3:
            app_name = str(args[0]) if args else ""
            window_title = str(args[1]) if len(args) > 1 else ""
            pid_val = args[2] if len(args) > 2 else 0
            try:
                pid = int(pid_val)
            except (ValueError, TypeError):
                pid = 0
            self._tracker._on_dbus_window_changed(app_name, window_title, pid)
            return True
        return False

    def introspect(self, path: str) -> str:  # noqa: N802, ARG002
        return (
            '<interface name="org.trackit.App">'
            '<method name="windowChanged">'
            '<arg name="app_name" type="s" direction="in"/>'
            '<arg name="window_title" type="s" direction="in"/>'
            '<arg name="pid" type="i" direction="in"/>'
            '</method>'
            '</interface>'
        )


class WindowTrackerService(QObject):
    window_changed = Signal(WindowInfo)
    tracking_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running: bool = False
        self._current_window: WindowInfo | None = None
        self._bus: QDBusConnection | None = None
        self._kwin_scripting: QDBusInterface | None = None
        self._handler: _DBusHandler | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_window(self) -> WindowInfo | None:
        return self._current_window

    def start(self) -> bool:
        if self._running:
            return True

        self._install_kwin_script()
        script_loaded = self._load_kwin_script()

        self._bus = QDBusConnection.sessionBus()
        ok = self._bus.registerService(TRACKIT_SERVICE)
        if not ok:
            logger.warning("Could not register D-Bus service %s", TRACKIT_SERVICE)

        self._handler = _DBusHandler(self)
        registered = self._bus.registerVirtualObject(TRACKIT_PATH, self._handler)

        self._running = True
        logger.info(
            "WindowTrackerService started (KWin script=%s, D-Bus=%s)",
            "loaded" if script_loaded else "failed",
            "registered" if (ok and registered) else "warning",
        )
        return True

    def stop(self) -> None:
        self._running = False
        if self._bus is not None and self._handler is not None:
            self._bus.unregisterObject(TRACKIT_PATH)
            self._bus.unregisterService(TRACKIT_SERVICE)
            self._bus = None
            self._handler = None
        if self._kwin_scripting is not None:
            self._unload_kwin_script()
        logger.info("WindowTrackerService stopped")

    def _on_dbus_window_changed(self, app_name: str, window_title: str, pid: int) -> None:
        log_message = f"Window changed: {app_name} - {window_title}"
        logger.info(log_message)
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

    def _install_kwin_script(self) -> None:
        """Write bundled KWin script files to user's KWin scripts directory."""
        try:
            code_dir = SCRIPT_INSTALL_DIR / "contents" / "code"
            code_dir.mkdir(parents=True, exist_ok=True)

            (SCRIPT_INSTALL_DIR / "metadata.json").write_text(KWIN_METADATA_JSON)
            (code_dir / "main.js").write_text(KWIN_SCRIPT_JS)
            logger.info("KWin script installed to %s", SCRIPT_INSTALL_DIR)
        except OSError as e:
            logger.warning("Failed to install KWin script: %s", e)

    def _load_kwin_script(self) -> bool:
        try:
            conn = QDBusConnection.sessionBus()
            iface = QDBusInterface(KWIN_SERVICE, KWIN_SCRIPTING_PATH, KWIN_SCRIPTING_IFACE, conn)
            if not iface.isValid():
                logger.warning("KWin Scripting D-Bus interface not available")
                return False

            script_path = str(SCRIPT_INSTALL_DIR / "contents" / "code" / "main.js")
            msg: QDBusMessage = iface.call("loadScript", script_path)
            if msg.type() == QDBusMessage.MessageType.ErrorMessage:
                logger.warning("Failed to load KWin script: %s", msg.errorMessage())
                return False

            script_id = msg.arguments()[0] if msg.arguments() else -1
            logger.info("KWin script loaded (id=%d)", script_id)
            self._kwin_scripting = iface
            return True
        except Exception as e:
            logger.warning("Failed to load KWin script: %s", e)
            return False

    def _unload_kwin_script(self) -> None:
        try:
            conn = QDBusConnection.sessionBus()
            iface = QDBusInterface(KWIN_SERVICE, KWIN_SCRIPTING_PATH, KWIN_SCRIPTING_IFACE, conn)
            iface.call("unloadScript", "trackit")
            logger.info("KWin script unloaded")
        except Exception as e:
            logger.debug("Failed to unload KWin script: %s", e)
