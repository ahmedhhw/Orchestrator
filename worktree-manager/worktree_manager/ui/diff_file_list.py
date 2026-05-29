from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

_LIST_STYLE = (
    "QListWidget::item:selected {"
    "  background-color: #2980b9;"
    "  color: white;"
    "}"
    "QListWidget::item:hover:!selected {"
    "  background-color: #f0f0f0;"
    "}"
)

_HIDE_STYLE = (
    "QPushButton {"
    "  padding: 2px 6px;"
    "  border: 1px solid #d0d0d0;"
    "  border-radius: 4px;"
    "  background-color: transparent;"
    "  color: #888;"
    "  font-size: 11px;"
    "}"
    "QPushButton:hover {"
    "  background-color: #f0f0f0;"
    "  border-color: #aaa;"
    "  color: #444;"
    "}"
)


class _KeyInterceptList(QListWidget):
    """QListWidget that intercepts ↑/↓/←/→/O and delegates to DiffFileList."""
    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self._owner = owner

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key_Down:
            self._owner.select_next()
        elif key == Qt.Key_Up:
            self._owner.select_prev()
        elif key == Qt.Key_Right:
            if self._owner._focus_right_cb:
                self._owner._focus_right_cb()
        elif key == Qt.Key_O:
            if self._owner._live_mode and self._owner._open_file_cb:
                self._owner._open_file_cb()
        else:
            super().keyPressEvent(event)


class DiffFileList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_selected_cb = None
        self._focus_right_cb = None
        self._open_file_cb = None
        self._hide_cb = None
        self._live_mode = False
        self._files = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("🔍 Filter...")
        layout.addWidget(self._filter)

        self._list_widget = _KeyInterceptList(self)
        self._list_widget.setSelectionMode(QListWidget.SingleSelection)
        self._list_widget.setStyleSheet(_LIST_STYLE)
        layout.addWidget(self._list_widget)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.addStretch(1)
        self._hide_btn = QPushButton("‹")
        self._hide_btn.setToolTip("Hide file list")
        self._hide_btn.setStyleSheet(_HIDE_STYLE)
        self._hide_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._hide_btn.setFixedSize(28, 22)
        self._hide_btn.clicked.connect(self._on_hide_clicked)
        bottom_row.addWidget(self._hide_btn)
        layout.addLayout(bottom_row)

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

    def on_hide(self, callback) -> None:
        self._hide_cb = callback

    def _on_hide_clicked(self) -> None:
        if self._hide_cb:
            self._hide_cb()

    def on_file_selected(self, callback) -> None:
        self._file_selected_cb = callback

    def on_focus_right(self, callback) -> None:
        self._focus_right_cb = callback

    def on_open_file(self, callback) -> None:
        self._open_file_cb = callback

    def set_live_mode(self, live: bool) -> None:
        self._live_mode = live

    def select_next(self) -> None:
        count = self._list_widget.count()
        if count == 0:
            return
        current = self._list_widget.currentRow()
        self._list_widget.setCurrentRow((current + 1) % count)

    def select_prev(self) -> None:
        count = self._list_widget.count()
        if count == 0:
            return
        current = self._list_widget.currentRow()
        self._list_widget.setCurrentRow((current - 1) % count)

    def focus(self) -> None:
        self._list_widget.setFocus()

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
