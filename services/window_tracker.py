import logging
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from models.window_info import WindowInfo

logger = logging.getLogger(__name__)

KWIN_SERVICE = "org.kde.KWin"
KWIN_SCRIPTING_PATH = "/Scripting"
KWIN_SCRIPTING_IFACE = "org.kde.kwin.Scripting"

POLL_INTERVAL_MS = 1000

SCRIPT_INSTALL_DIR = Path.home() / ".local" / "share" / "kwin" / "scripts" / "trackit"

KWIN_SCRIPT_JS = """\
function notify() {
    var w = workspace.activeWindow;
    if (!w) return;
    var info = JSON.stringify({
        app: w.resourceClass || w.resourceName || "",
        title: w.caption || ""
    });
    callDBus("org.trackit.App", "/org/trackit/App", "org.trackit.App", "windowChangedJson", info);
}
workspace.windowActivated.connect(notify);
"""

KWIN_METADATA_JSON = """\
{
    "KPlugin": {
        "Name": "trackit",
        "EnabledByDefault": true
    },
    "X-Plasma-API": "javascript",
    "X-Plasma-MainScript": "code/main.js"
}
"""


class WindowTrackerService(QObject):
    window_changed = Signal(WindowInfo)
    tracking_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running: bool = False
        self._current_window: WindowInfo | None = None
        self._timer: QTimer | None = None
        self._kwin_scripting: QDBusInterface | None = None

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
        self._load_kwin_script()

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
        if self._kwin_scripting is not None:
            self._unload_kwin_script()
        logger.info("WindowTrackerService stopped")

    def _poll(self) -> None:
        try:
            conn = QDBusConnection.sessionBus()
            iface = QDBusInterface(KWIN_SERVICE, "/KWin", KWIN_SERVICE, conn)
            if not iface.isValid():
                return
            msg: QDBusMessage = iface.call("getWindowInfo", "")
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
            raw_pid = props.get("pid", 0)
            pid = 0
            if isinstance(raw_pid, int) and not isinstance(raw_pid, bool):
                pid = raw_pid
            elif isinstance(raw_pid, str) and raw_pid:
                try:
                    pid = int(raw_pid)
                except ValueError:
                    pid = 0
            if app_name or window_title:
                self._on_window_info(app_name, window_title, pid)
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

    def _install_kwin_script(self) -> None:
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

            # Explicitly start scripts
            iface.call("start")

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
