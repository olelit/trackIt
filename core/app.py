import json
import logging
import sys
from pathlib import Path

from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusVirtualObject
from PySide6.QtWidgets import QApplication

from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService

logger = logging.getLogger(__name__)


class _DebugDBusHandler(QDBusVirtualObject):
    """Accepts manual window changes via dbus-send for testing."""

    def __init__(self, tracker: WindowTrackerService) -> None:
        super().__init__()
        self._tracker = tracker

    def handleMessage(self, message: QDBusMessage, connection: QDBusConnection) -> bool:  # noqa: N802
        try:
            method = message.member()
            args = message.arguments()
            if method == "windowChangedJson" and args:
                data = json.loads(str(args[0]))
                app_name = data.get("app", "")
                window_title = data.get("title", "")
                if app_name:
                    self._tracker._on_window_info(app_name, window_title, 0)
                reply = message.createReply()
                connection.send(reply)
                return True
        except Exception:
            pass
        return False

    def introspect(self, path: str) -> str:  # noqa: N802, ARG002
        return (
            '<interface name="org.trackit.App">'
            '<method name="windowChangedJson">'
            '<arg name="json" type="s" direction="in"/>'
            '</method>'
            '</interface>'
        )


_dbus_handler: QDBusVirtualObject | None = None


def _register_dbus_handler(tracker: WindowTrackerService) -> None:
    global _dbus_handler
    bus = QDBusConnection.sessionBus()
    ok = bus.registerService("org.trackit.App")
    if ok:
        _dbus_handler = _DebugDBusHandler(tracker)
        bus.registerVirtualObject("/org/trackit/App", _dbus_handler)
        logger.info("D-Bus handler registered — use dbus-send for manual window injection")
    else:
        logger.warning("Could not register D-Bus service (may already be running)")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname).4s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def get_db_path() -> str:
    data_dir = Path.home() / ".local" / "share" / "trackit"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "trackit.db")


def create_app() -> QApplication:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("TrackIt")
    app.setOrganizationName("TrackIt")
    return app


def create_services(storage: StorageService) -> tuple[WindowTrackerService, ActivityService, TimeTrackingService]:
    window_tracker = WindowTrackerService()
    activity_service = ActivityService(storage)
    time_tracking = TimeTrackingService(storage, window_tracker, activity_service)
    return window_tracker, activity_service, time_tracking


def main() -> None:
    app = create_app()
    db_path = get_db_path()
    logger.info("Starting TrackIt (db=%s)", db_path)

    storage = StorageService(db_path)
    window_tracker, activity_service, time_tracking = create_services(storage)

    _register_dbus_handler(window_tracker)

    from ui.main_window import MainWindow
    window = MainWindow(activity_service, window_tracker, storage, time_tracking)
    window.show()

    window_tracker.start()

    exit_code = app.exec()
    window_tracker.stop()
    logger.info("TrackIt exiting (code=%d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
