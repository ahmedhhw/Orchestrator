from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractScrollArea, QApplication, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from worktree_manager.command_runner import RunHandle, RunStatus

_STATUS_COLORS = {
    RunStatus.RUNNING: "green",
    RunStatus.STOPPED: "gray",
    RunStatus.ERROR: "red",
}

_STATUS_DOTS = {
    RunStatus.RUNNING: "●",
    RunStatus.STOPPED: "○",
    RunStatus.ERROR: "✕",
}


class CommandPane(QWidget):
    def __init__(self, parent, handle: RunHandle, on_maximize, on_stop,
                 on_restart, on_remove=None, show_popout_btn=True):
        super().__init__(parent)
        self._handle = handle
        self._run_id = handle.run_id
        self._on_maximize = on_maximize
        self._on_stop = on_stop
        self._on_restart = on_restart
        self._on_remove = on_remove
        self._show_popout_btn = show_popout_btn
        self._status = handle.status
        self._find_matches: list[int] = []
        self._find_cursor = 0
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(2)

        header = QHBoxLayout()
        self._dot = QLabel(_STATUS_DOTS[self._status])
        self._dot.setStyleSheet(f"color: {_STATUS_COLORS[self._status]};")
        self._dot.setFixedWidth(16)
        header.addWidget(self._dot)

        wt_name = self._handle.worktree_path.split("/")[-1]
        self._label = QLabel(
            f"{self._handle.cmd_name} · {self._handle.repo_name} : {wt_name}"
        )
        header.addWidget(self._label, 1)

        if self._show_popout_btn:
            header.addWidget(self._mk_btn("⤢", self.trigger_maximize))
        header.addWidget(self._mk_btn("⟳", self.trigger_restart))
        header.addWidget(self._mk_btn("■", self.trigger_stop))
        header.addWidget(self._mk_btn("⎘", self.trigger_copy))
        header.addWidget(self._mk_btn("🔍", self.show_find_bar))
        header.addWidget(self._mk_btn("✕", self.trigger_remove))
        outer.addLayout(header)

        self._find_bar = QWidget()
        find_layout = QHBoxLayout(self._find_bar)
        find_layout.setContentsMargins(0, 0, 0, 0)
        self._find_entry = QLineEdit()
        self._find_entry.setPlaceholderText("🔍 search...")
        self._find_entry.textChanged.connect(self._apply_find)
        self._find_entry.returnPressed.connect(self._find_next)
        find_layout.addWidget(self._find_entry, 1)
        self._find_count_label = QLabel("")
        self._find_count_label.setFixedWidth(80)
        find_layout.addWidget(self._find_count_label)
        find_layout.addWidget(self._mk_btn("↑", self._find_prev))
        find_layout.addWidget(self._mk_btn("↓", self._find_next))
        find_layout.addWidget(self._mk_btn("×", self.hide_find_bar))
        self._find_bar_visible = False
        self._find_bar.setVisible(False)
        outer.addWidget(self._find_bar)

        self._textbox = QPlainTextEdit()
        self._textbox.setReadOnly(True)
        self._textbox.setMinimumHeight(140)
        outer.addWidget(self._textbox, 1)

    def _mk_btn(self, label, handler):
        b = QPushButton(label)
        b.setFixedWidth(28)
        b.clicked.connect(lambda _checked=False: handler())
        return b

    # --- public API ---

    def header_text(self) -> str:
        return self._label.text()

    def append_line(self, line: str) -> None:
        self._textbox.appendPlainText(line)
        sb = self._textbox.verticalScrollBar()
        sb.setValue(sb.maximum())
        if self._find_bar.isVisible():
            self._apply_find()

    def get_output_text(self) -> str:
        return self._textbox.toPlainText()

    def clear_output(self) -> None:
        self._textbox.clear()

    def set_status(self, status: RunStatus) -> None:
        self._status = status
        self._dot.setText(_STATUS_DOTS[status])
        self._dot.setStyleSheet(f"color: {_STATUS_COLORS[status]};")

    def status_dot_color(self) -> str:
        return _STATUS_COLORS[self._status]

    def update_run_id(self, run_id: str) -> None:
        self._run_id = run_id

    def update_callbacks(self, on_stop, on_restart, on_remove=None) -> None:
        self._on_stop = on_stop
        self._on_restart = on_restart
        if on_remove is not None:
            self._on_remove = on_remove

    def trigger_remove(self) -> None:
        if self._on_remove:
            self._on_remove()

    def trigger_stop(self) -> None:
        self._on_stop()

    def trigger_restart(self) -> None:
        self._on_restart()

    def trigger_maximize(self) -> None:
        self._on_maximize(self)

    def trigger_copy(self) -> None:
        QApplication.clipboard().setText(self.get_output_text())

    def show_find_bar(self) -> None:
        self._find_bar_visible = True
        self._find_bar.setVisible(True)
        self._find_entry.setFocus()
        self._apply_find()

    def hide_find_bar(self) -> None:
        self._find_bar_visible = False
        self._find_bar.setVisible(False)
        self._textbox.setExtraSelections([])
        self._find_count_label.setText("")

    def find_bar_visible(self) -> bool:
        return self._find_bar_visible

    def find(self, query: str) -> int:
        self._find_matches = []
        self._textbox.setExtraSelections([])
        if not query:
            return 0
        doc = self._textbox.document()
        text = doc.toPlainText().lower()
        q = query.lower()
        start = 0
        while True:
            idx = text.find(q, start)
            if idx == -1:
                break
            self._find_matches.append(idx)
            start = idx + len(q)
        selections = []
        for pos in self._find_matches:
            cursor = QTextCursor(doc)
            cursor.setPosition(pos)
            cursor.setPosition(pos + len(query), QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("yellow"))
            fmt.setForeground(QColor("black"))
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            selections.append(sel)
        self._textbox.setExtraSelections(selections)
        return len(self._find_matches)

    # --- private ---

    def _apply_find(self) -> None:
        query = self._find_entry.text() if self._find_bar.isVisible() else ""
        count = self.find(query)
        self._find_cursor = 0
        self._find_count_label.setText(
            f"{count} match{'es' if count != 1 else ''}" if query else ""
        )

    def _find_next(self) -> None:
        if not self._find_matches:
            return
        self._find_cursor = (self._find_cursor + 1) % len(self._find_matches)
        cursor = self._textbox.textCursor()
        cursor.setPosition(self._find_matches[self._find_cursor])
        self._textbox.setTextCursor(cursor)

    def _find_prev(self) -> None:
        if not self._find_matches:
            return
        self._find_cursor = (self._find_cursor - 1) % len(self._find_matches)
        cursor = self._textbox.textCursor()
        cursor.setPosition(self._find_matches[self._find_cursor])
        self._textbox.setTextCursor(cursor)
