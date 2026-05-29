from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt


class DiffFileList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_selected_cb = None
        self._files = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("🔍 Filter...")
        layout.addWidget(self._filter)

        self._list_widget = QListWidget()
        layout.addWidget(self._list_widget)

        self._filter.textChanged.connect(self._apply_filter)
        self._list_widget.currentRowChanged.connect(self._on_row_changed)

    def set_files(self, files: list) -> None:
        self._files = files
        self._list_widget.clear()
        for f in files:
            text = f"{f.path} [{f.status}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, f.path)
            self._list_widget.addItem(item)
        self._apply_filter(self._filter.text())

    def on_file_selected(self, callback) -> None:
        self._file_selected_cb = callback

    def _apply_filter(self, text: str) -> None:
        lower = text.lower()
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            item.setHidden(bool(lower) and lower not in item.text().lower())

    def _on_row_changed(self, row: int) -> None:
        if row < 0:
            return
        item = self._list_widget.item(row)
        if item and self._file_selected_cb:
            self._file_selected_cb(item.data(Qt.UserRole))
