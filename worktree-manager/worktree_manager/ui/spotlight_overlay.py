from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QLineEdit, QListWidget, QVBoxLayout, QWidget,
)

from worktree_manager.spotlight.action_parser import ActionParser


class SpotlightOverlay(QWidget):
    def __init__(self, parser: ActionParser, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.resize(520, 320)

        self._parser = parser

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(">")
        self._edit.textChanged.connect(self._on_text_changed)
        self._edit.installEventFilter(self)
        layout.addWidget(self._edit)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        self._refresh("")

    def _on_text_changed(self, text: str) -> None:
        self._refresh(text)

    def _refresh(self, text: str) -> None:
        result = self._parser.parse(text)
        self._list.clear()
        for s in result.suggestions:
            self._list.addItem(s)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _maybe_execute(self) -> None:
        result = self._parser.parse(self._edit.text())
        if result.action is None:
            return
        if self._list.count() == 0:
            return
        item = self._list.currentItem()
        if item is None:
            return
        value = item.text()
        slot = result.action.slots[0] if result.action.slots else None
        args = {slot.name: value} if slot else {}
        result.action.runner(args)
        self.hide()

    def eventFilter(self, obj, event):
        if obj is self._edit and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                self.hide()
                return True
            if key == Qt.Key_Down:
                row = min(self._list.currentRow() + 1, self._list.count() - 1)
                if row >= 0:
                    self._list.setCurrentRow(row)
                return True
            if key == Qt.Key_Up:
                row = max(self._list.currentRow() - 1, 0)
                if self._list.count() > 0:
                    self._list.setCurrentRow(row)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._maybe_execute()
                return True
        return super().eventFilter(obj, event)

    def show_centered_over(self, parent: QWidget) -> None:
        geo = parent.geometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() // 4)
        self.move(x, y)
        self._edit.clear()
        self._refresh("")
        self.show()
        self._edit.setFocus()
