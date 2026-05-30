import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout,
    QLabel, QMenu, QInputDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from models.activity import Activity
from services.activity_service import ActivityService

logger = logging.getLogger(__name__)


class ActivityListWidget(QWidget):
    activity_selected = Signal(int)

    def __init__(self, activity_service: ActivityService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._activity_service = activity_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        title = QLabel("Activities")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.clicked.connect(self._on_add_clicked)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self._list_widget = QListWidget()
        self._list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list_widget)

        self._activity_service.activity_added.connect(self._on_activity_added)
        self._activity_service.activity_updated.connect(self._on_activity_updated)
        self._activity_service.activity_deleted.connect(self._on_activity_deleted)
        self._activity_service.active_activity_changed.connect(self._refresh_list)

        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list_widget.clear()
        for activity in self._activity_service.get_all_activities():
            self._add_activity_item(activity)

    def _add_activity_item(self, activity: Activity) -> None:
        active_marker = " ●" if activity.is_active else ""
        hours = activity.total_duration_seconds // 3600
        minutes = (activity.total_duration_seconds % 3600) // 60
        time_str = f"{hours}h {minutes:02d}m" if hours > 0 else f"{minutes}m"

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, activity.id)
        item.setSizeHint(item.sizeHint().expandedTo(item.sizeHint()))

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(4, 2, 4, 2)

        label = QLabel(f"{activity.name}{active_marker}  [{time_str}]")
        row_layout.addWidget(label)
        row_layout.addStretch()

        kebab_btn = self._create_kebab_button(activity)
        row_layout.addWidget(kebab_btn)

        self._list_widget.addItem(item)
        self._list_widget.setItemWidget(item, row_widget)

    def _create_kebab_button(self, activity: Activity) -> QPushButton:
        btn = QPushButton("\u22ee")
        btn.setFixedWidth(30)
        btn.clicked.connect(lambda checked=False, a=activity: self._show_kebab_menu(a, btn))
        return btn

    def _show_kebab_menu(self, activity: Activity, button: QPushButton) -> None:
        menu = QMenu(self)

        set_active_action = QAction("Set Active", menu)
        set_active_action.triggered.connect(lambda: self._activity_service.set_active(activity.id))
        menu.addAction(set_active_action)

        rename_action = QAction("Rename", menu)
        rename_action.triggered.connect(lambda: self._rename_activity(activity))
        menu.addAction(rename_action)

        export_action = QAction("Export (stub)", menu)
        export_action.triggered.connect(lambda: logger.info("Export stub for activity %d", activity.id))
        menu.addAction(export_action)

        duplicate_action = QAction("Duplicate (stub)", menu)
        duplicate_action.triggered.connect(lambda: logger.info("Duplicate stub for activity %d", activity.id))
        menu.addAction(duplicate_action)

        menu.addSeparator()

        delete_action = QAction("Delete", menu)
        delete_action.triggered.connect(lambda: self._activity_service.delete_activity(activity.id))
        menu.addAction(delete_action)

        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _rename_activity(self, activity: Activity) -> None:
        new_name, ok = QInputDialog.getText(
            self, "Rename Activity", "Name:", text=activity.name
        )
        if ok and new_name.strip():
            self._activity_service.rename_activity(activity.id, new_name.strip())

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        activity_id = item.data(Qt.ItemDataRole.UserRole)
        if activity_id is not None:
            self.activity_selected.emit(int(activity_id))

    def _on_add_clicked(self) -> None:
        self._activity_service.create_activity("New Activity")

    def _on_activity_added(self, activity: Activity) -> None:
        self._refresh_list()

    def _on_activity_updated(self, activity: Activity) -> None:
        self._refresh_list()

    def _on_activity_deleted(self, activity_id: int) -> None:
        self._refresh_list()
