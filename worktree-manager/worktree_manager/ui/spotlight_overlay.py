from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QListWidget, QVBoxLayout, QWidget,
)

from worktree_manager.spotlight.action_parser import ActionParser

# Maps slot names to human-friendly plural captions.
SLOT_CAPTIONS: dict[str, str] = {
    "repo": "REPOS",
    "worktree": "WORKTREES",
    "branch": "BRANCHES",
    "cmd": "COMMANDS",
    "name": "PROJECTS",
    "editor": "EDITORS",
}


class SpotlightOverlay(QWidget):
    def __init__(
        self,
        parser: ActionParser,
        parent: QWidget | None = None,
        on_action_executed=None,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
        self.setMinimumSize(520, 320)
        self._parser = parser
        self._on_action_executed = on_action_executed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(">")
        self._edit.textChanged.connect(self._on_text_changed)
        self._edit.installEventFilter(self)
        layout.addWidget(self._edit)

        self._caption = QLabel()
        self._caption.setObjectName("caption_label")
        self._caption.hide()
        layout.addWidget(self._caption)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, 1)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self._refresh("")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def error_text(self) -> str:
        return self._error_label.text() if not self._error_label.isHidden() else ""

    def show_centered_over(self, parent: QWidget) -> None:
        geo = parent.geometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() // 4)
        self.move(x, y)
        self._edit.clear()
        self._set_error("")
        self._set_invalid(False)
        self._refresh("")
        self.show()
        self._edit.setFocus()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_error(self, message: str) -> None:
        if message:
            self._error_label.setText(message)
            self._error_label.show()
        else:
            self._error_label.hide()
            self._error_label.setText("")

    def _set_invalid(self, flag: bool) -> None:
        self._edit.setProperty("invalid", flag)
        style = self._edit.style()
        if style is not None:
            style.unpolish(self._edit)
            style.polish(self._edit)

    def _on_text_changed(self, text: str) -> None:
        self._set_error("")
        self._set_invalid(False)
        self._refresh(text)

    def _refresh(self, text: str) -> None:
        result = self._parser.parse(text)
        self._list.clear()
        for s in result.suggestions:
            self._list.addItem(s)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        self._render_caption(result)

    def _render_caption(self, result) -> None:
        if not result.suggestions:
            self._caption.hide()
            return
        if result.action is None:
            cap = "COMMANDS"
        elif result.slot_index < len(result.action.slots):
            slot_name = result.action.slots[result.slot_index].name
            cap = SLOT_CAPTIONS.get(slot_name, slot_name.upper())
        else:
            cap = "COMMANDS"
        self._caption.setText(cap)
        self._caption.show()

    def _commit(self, text: str, row_text: str) -> str:
        """Strip the active filter_text from `text`, append `row_text + ' '`."""
        result = self._parser.parse(text)
        ft = result.filter_text
        base = text[: len(text) - len(ft)] if ft else text
        if base and not base.endswith(" "):
            base += " "
        return base + row_text + " "

    @staticmethod
    def _result_is_fully_committed(result) -> bool:
        """Return True when `result` represents an executable, fully-committed command."""
        return (
            result.action is not None
            and result.executable
            and (not result.action.slots or result.slot_index == len(result.action.slots))
        )

    def _execute_result(self, result) -> None:
        """Run the action described by `result` and hide the overlay."""
        args = dict(result.committed_args)
        result.action.runner(args)
        if self._on_action_executed:
            self._on_action_executed(result.action.name, args)
        self.hide()

    def _commit_or_execute(self) -> None:
        text = self._edit.text()
        result = self._parser.parse(text)

        # 1. Exact nickname → run stored action.
        if result.completion_kind == "nickname" and result.nickname_action_name:
            spec = self._parser._registry.get_by_name(result.nickname_action_name)
            if spec is None:
                self._set_error("Unknown command")
                return
            args = dict(result.nickname_args or {})
            spec.runner(args)
            if self._on_action_executed:
                self._on_action_executed(result.nickname_action_name, args)
            self.hide()
            return

        # 2. Complete command (all slots committed) → execute.
        if self._result_is_fully_committed(result):
            self._execute_result(result)
            return

        # 3. Incomplete + a row highlighted → commit that row and advance.
        item = self._list.currentItem()
        if result.suggestions and item is not None:
            row_text = item.text()
            # If the row is a nickname, execute it directly. _commit would append a trailing space
            # which prevents the parser's exact-nickname check from firing on a second Enter.
            nick_store = self._parser._nickname_store
            if nick_store is not None:
                entry = nick_store.get(row_text)
                if entry is not None:
                    spec = self._parser._registry.get_by_name(entry.action_name)
                    if spec is not None:
                        args = dict(entry.args)
                        spec.runner(args)
                        if self._on_action_executed:
                            self._on_action_executed(entry.action_name, args)
                        self.hide()
                        return
            self._edit.setText(self._commit(text, row_text))
            return

        # 4. Nothing to commit → flag invalid.
        self._set_invalid(True)
        self._set_error("No matching option")

    def _on_item_clicked(self, item) -> None:
        """Single click: commit the clicked row; if that completes the command, execute immediately."""
        self._list.setCurrentItem(item)
        text = self._edit.text()
        result = self._parser.parse(text)

        # Nickname: delegate directly — _commit would append a trailing space and break the match.
        if result.completion_kind == "nickname":
            self._commit_or_execute()
            return

        # Look ahead: if this click would commit (path 3) and the committed text
        # would be immediately executable, do commit+execute in one shot.
        if result.suggestions and not self._result_is_fully_committed(result):
            new_text = self._commit(text, item.text())
            new_result = self._parser.parse(new_text)
            if self._result_is_fully_committed(new_result):
                self._edit.setText(new_text)
                self._execute_result(new_result)
                return

        self._commit_or_execute()

    # ------------------------------------------------------------------
    # Event filter
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._edit and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Escape:
                self.hide()
                return True
            if key == Qt.Key_Tab:
                # Tab does nothing in the new model.
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._commit_or_execute()
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
