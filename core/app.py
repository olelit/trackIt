import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from services.activity_service import ActivityService
from services.storage_service import StorageService
from services.time_tracking import TimeTrackingService
from services.window_tracker import WindowTrackerService

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
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

    from ui.main_window import MainWindow
    window = MainWindow(activity_service, window_tracker, storage)
    window.show()

    window_tracker.start()

    exit_code = app.exec()
    window_tracker.stop()
    logger.info("TrackIt exiting (code=%d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
