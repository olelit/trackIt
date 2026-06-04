import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.app_info import AppInfo
from services.app_info_service import AppInfoService

logger = logging.getLogger(__name__)


SUMMARY_TITLE_MAX = 80
ARGV_DISPLAY_MAX = 200


class DebugPanel(QWidget):
    def __init__(
        self,
        app_info_service: AppInfoService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = app_info_service
        self._collapsed = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row: title + collapse toggle
        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 0)
        title = QLabel("Debug")
        title.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self._toggle_button = QPushButton("▼")
        self._toggle_button.setFixedWidth(28)
        self._toggle_button.setStyleSheet("color: #888; font-size: 11px;")
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        header.addWidget(self._toggle_button)
        layout.addLayout(header)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Summary line (always visible)
        self._summary_label = QLabel("Window: — | RAM: —")
        self._summary_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px 8px;")
        self._summary_label.setWordWrap(False)
        self._summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._summary_label)

        # Details (visibility toggled)
        self._details = QWidget()
        details_layout = QVBoxLayout(self._details)
        details_layout.setContentsMargins(8, 4, 8, 4)
        details_layout.setSpacing(2)

        self._pid_label = QLabel("PID: —")
        self._pid_label.setStyleSheet("color: #888; font-size: 11px;")
        self._pid_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self._pid_label)

        self._argv_label = QLabel("Argv: —")
        self._argv_label.setStyleSheet("color: #888; font-size: 11px;")
        self._argv_label.setWordWrap(True)
        self._argv_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self._argv_label)

        self._opened_label = QLabel("Opened: —")
        self._opened_label.setStyleSheet("color: #888; font-size: 11px;")
        self._opened_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_layout.addWidget(self._opened_label)

        layout.addWidget(self._details)
        self._details.setVisible(False)

        self._service.info_updated.connect(self._on_info_updated)

        logger.info("DebugPanel created")

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._details.setVisible(not collapsed)
        self._toggle_button.setText("▼" if collapsed else "▲")

    def _on_toggle_clicked(self) -> None:
        self.set_collapsed(not self._collapsed)

    def _on_info_updated(self, info: AppInfo | None) -> None:
        if info is None:
            self._summary_label.setText("Window: — | RAM: —")
            self._pid_label.setText("PID: —")
            self._argv_label.setText("Argv: —")
            self._opened_label.setText("Opened: —")
            return

        title = info.window_title
        if len(title) > SUMMARY_TITLE_MAX:
            title = title[: SUMMARY_TITLE_MAX - 1] + "…"
        ram = f"{info.ram_mb} MB" if info.ram_mb is not None else "—"
        self._summary_label.setText(f"Window: {info.app_name} — {title} | RAM: {ram}")

        pid_text = str(info.pid) if info.pid is not None else "—"
        self._pid_label.setText(f"PID: {pid_text}")

        if info.argv:
            argv_text = " ".join(info.argv)
            if len(argv_text) > ARGV_DISPLAY_MAX:
                argv_text = argv_text[: ARGV_DISPLAY_MAX - 1] + "…"
            self._argv_label.setText(f"Argv: {argv_text}")
        else:
            self._argv_label.setText("Argv: —")

        opened = info.opened_path if info.opened_path is not None else "—"
        self._opened_label.setText(f"Opened: {opened}")
