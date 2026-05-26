from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QListWidget, QVBoxLayout, QWidget,
)

from worktree_manager.spotlight.action_parser import ActionParser


def _longest_common_prefix(items: list[str]) -> str:
    if not items:
        return ""
    out = items[0]
    for s in items[1:]:
        i = 0
        while i < len(out) and i < len(s) and out[i].lower() == s[i].lower():
            i += 1
        out = out[:i]
        if not out:
            return ""
    return out


class _GhostLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ghost: str = ""

    def set_ghost_text(self, text: str) -> None:
        if text == self._ghost:
            return
        self._ghost = text
        self.update()

    def ghost_text(self) -> str:
        return self._ghost

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._ghost:
            return
        painter = QPainter(self)
        painter.setPen(QColor(150, 150, 150))
        rect = self.cursorRect()
        x = rect.right() + 1
        w = max(0, self.width() - x - 4)
        painter.drawText(
            QRect(x, 0, w, self.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self._ghost,
        )
        painter.end()


class SpotlightOverlay(QWidget):
    def __init__(self, parser: ActionParser, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.resize(520, 320)

        self._parser = parser
        self._tab_cycle: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._edit = _GhostLineEdit()
        self._edit.setPlaceholderText(">")
        self._edit.textChanged.connect(self._on_text_changed)
        self._edit.installEventFilter(self)
        layout.addWidget(self._edit)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self._refresh("")

    def error_text(self) -> str:
        return self._error_label.text() if not self._error_label.isHidden() else ""

    def _set_error(self, message: str) -> None:
        if message:
            self._error_label.setText(message)
            self._error_label.show()
        else:
            self._error_label.hide()
            self._error_label.setText("")

    def _on_text_changed(self, text: str) -> None:
        self._tab_cycle = None
        self._set_error("")
        self._refresh(text)

    def _refresh(self, text: str) -> None:
        result = self._parser.parse(text)
        self._list.clear()
        for s in result.suggestions:
            self._list.addItem(s)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

        # Only show common-prefix ghost when not in a Tab cycle.
        if self._tab_cycle is None:
            ghost = ""
            if result.suggestions:
                common = _longest_common_prefix(result.suggestions)
                ft = result.filter_text
                if common:
                    if ft and common.lower().startswith(ft.lower()) and len(common) > len(ft):
                        ghost = common[len(ft):]
                    elif not ft:
                        ghost = common
            self._edit.set_ghost_text(ghost)

    def _commit_ghost(self) -> None:
        ghost = self._edit.ghost_text()
        if not ghost:
            return
        self._edit.set_ghost_text("")
        self._tab_cycle = None
        current = self._edit.text()
        # Insert a space separator when ghost is a new token rather than a suffix.
        result = self._parser.parse(current)
        if result.filter_text == "" and current and not current.endswith(" "):
            separator = " "
        else:
            separator = ""
        self._edit.setText(current + separator + ghost)

    def _handle_tab(self) -> None:
        text = self._edit.text()
        result = self._parser.parse(text)
        suggestions = result.suggestions
        if not suggestions:
            return

        ft = result.filter_text
        base = text[: len(text) - len(ft)] if ft else text

        common = _longest_common_prefix(suggestions)

        if len(suggestions) == 1:
            # If ghost is already showing for this single option, commit it.
            if self._edit.ghost_text():
                self._commit_ghost()
                return
            # Ghost not yet shown — set it so the user sees it before committing.
            completion = suggestions[0]
            ghost = completion[len(ft):]
            suffix = self._tab_suffix(result)
            self._tab_cycle = {
                "base": base,
                "candidates": suggestions,
                "idx": 0,
                "suffix": suffix,
            }
            self._edit.set_ghost_text(ghost + suffix)
            return

        if common and len(common) > len(ft) and common.lower().startswith(ft.lower()):
            ghost = common[len(ft):]
            self._tab_cycle = {
                "base": base,
                "candidates": suggestions,
                "idx": -1,
                "suffix": "",
            }
            self._edit.set_ghost_text(ghost)
            return

        # No common prefix: start/advance cycling through suggestions as ghost.
        if self._tab_cycle is not None and self._tab_cycle.get("cycling"):
            idx = (self._tab_cycle["idx"] + 1) % len(self._tab_cycle["candidates"])
        else:
            idx = 0
        completion = suggestions[idx]
        self._tab_cycle = {
            "base": base,
            "candidates": list(suggestions),
            "idx": idx,
            "suffix": "",
            "cycling": True,
        }
        self._edit.set_ghost_text(completion[len(ft):] if ft else completion)

    def _tab_suffix(self, result) -> str:
        if result.completion_kind == "keyword":
            return " "
        if result.completion_kind == "slot" and result.action is not None:
            if result.slot_index < len(result.action.slots) - 1:
                return " "
        return ""

    def _maybe_execute(self) -> None:
        # If ghost is showing, Enter commits it — nothing more.
        if self._edit.ghost_text():
            self._commit_ghost()
            return

        # No ghost: execute only if the command is complete.
        result = self._parser.parse(self._edit.text())
        if result.action is None:
            self._set_error("Unknown command")
            return

        args = dict(result.committed_args)
        if result.action.slots:
            if result.slot_index < len(result.action.slots):
                if self._list.count() == 0:
                    self._set_error("No matching option")
                    return
                item = self._list.currentItem()
                if item is None:
                    self._set_error("No option selected")
                    return
                slot = result.action.slots[result.slot_index]
                args[slot.name] = item.text()

        result.action.runner(args)
        self.hide()

    def eventFilter(self, obj, event):
        if obj is self._edit and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                self.hide()
                return True
            if key == Qt.Key_Tab:
                self._handle_tab()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._maybe_execute()
                return True
            if key in (Qt.Key_Down, Qt.Key_Up):
                if key == Qt.Key_Down:
                    row = min(self._list.currentRow() + 1, self._list.count() - 1)
                    if row >= 0:
                        self._list.setCurrentRow(row)
                else:
                    row = max(self._list.currentRow() - 1, 0)
                    if self._list.count() > 0:
                        self._list.setCurrentRow(row)
                return True
        return super().eventFilter(obj, event)

    def show_centered_over(self, parent: QWidget) -> None:
        geo = parent.geometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() // 4)
        self.move(x, y)
        self._edit.clear()
        self._tab_cycle = None
        self._set_error("")
        self._refresh("")
        self.show()
        self._edit.setFocus()
