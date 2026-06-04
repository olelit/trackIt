"""Shared pytest fixtures."""

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def qapp() -> QApplication:
    """Provide a real QApplication for widget tests.

    pytest-qt's qtbot fixture auto-creates a QApplication via its own
    qapp fixture, but it can return a QCoreApplication in some configs.
    This fixture forces QApplication so widget construction (e.g.
    QWidget, DebugPanel) is always safe, and ensures both service-level
    and UI-level tests share the same instance.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app
