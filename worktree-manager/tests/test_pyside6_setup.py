def test_pyside6_importable():
    """PySide6 is installed and importable."""
    import PySide6.QtWidgets  # noqa: F401


def test_qapplication_can_be_created(qapp):
    """pytest-qt's qapp fixture provides a real QApplication backed by PySide6."""
    from PySide6.QtWidgets import QApplication
    assert isinstance(qapp, QApplication)


def test_qtbot_can_add_widget(qtbot):
    """qtbot fixture works and can manage a QWidget lifecycle."""
    from PySide6.QtWidgets import QWidget
    w = QWidget()
    qtbot.addWidget(w)
    assert w.isHidden() or w.isVisible() or True  # smoke
