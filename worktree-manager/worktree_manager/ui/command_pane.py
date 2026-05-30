import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent, QTextCharFormat, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QAbstractScrollArea, QApplication, QComboBox, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QMessageBox, QPushButton, QStyle, QTextEdit, QVBoxLayout,
    QWidget,
)

from worktree_manager.ui.filterable_combo import FilterableComboBox

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


# Standard 8-color palette (normal + bright)
_ANSI_COLORS = [
    "#000000", "#cc0000", "#00aa00", "#aaaa00",
    "#0000cc", "#aa00aa", "#00aaaa", "#aaaaaa",
    "#555555", "#ff5555", "#55ff55", "#ffff55",
    "#5555ff", "#ff55ff", "#55ffff", "#ffffff",
]

_ANSI_RE = re.compile(r"\x1b\[([\d;]*)m")


def _ansi_color(index: int) -> QColor:
    if 0 <= index < len(_ANSI_COLORS):
        return QColor(_ANSI_COLORS[index])
    return QColor()


def _fmt_from_sgr(params: list[int]) -> tuple[QColor, QColor, bool, bool]:
    """Parse SGR params and return (fg, bg, bold, italic). QColor() means 'default'."""
    fg = QColor()
    bg = QColor()
    bold = False
    italic = False
    i = 0
    while i < len(params):
        p = params[i]
        if p == 0:
            fg, bg, bold, italic = QColor(), QColor(), False, False
        elif p == 1:
            bold = True
        elif p == 3:
            italic = True
        elif p == 22:
            bold = False
        elif p == 23:
            italic = False
        elif 30 <= p <= 37:
            fg = _ansi_color(p - 30)
        elif p == 38:
            if i + 1 < len(params) and params[i + 1] == 5 and i + 2 < len(params):
                idx = params[i + 2]
                fg = _256_color(idx)
                i += 2
            elif i + 1 < len(params) and params[i + 1] == 2 and i + 4 < len(params):
                fg = QColor(params[i + 2], params[i + 3], params[i + 4])
                i += 4
        elif p == 39:
            fg = QColor()
        elif 40 <= p <= 47:
            bg = _ansi_color(p - 40)
        elif p == 48:
            if i + 1 < len(params) and params[i + 1] == 5 and i + 2 < len(params):
                idx = params[i + 2]
                bg = _256_color(idx)
                i += 2
            elif i + 1 < len(params) and params[i + 1] == 2 and i + 4 < len(params):
                bg = QColor(params[i + 2], params[i + 3], params[i + 4])
                i += 4
        elif p == 49:
            bg = QColor()
        elif 90 <= p <= 97:
            fg = _ansi_color(p - 90 + 8)
        elif 100 <= p <= 107:
            bg = _ansi_color(p - 100 + 8)
        i += 1
    return fg, bg, bold, italic


def _256_color(idx: int) -> QColor:
    if idx < 16:
        return _ansi_color(idx)
    if idx < 232:
        idx -= 16
        b = idx % 6
        g = (idx // 6) % 6
        r = idx // 36
        to_byte = lambda v: 0 if v == 0 else 55 + v * 40
        return QColor(to_byte(r), to_byte(g), to_byte(b))
    gray = 8 + (idx - 232) * 10
    return QColor(gray, gray, gray)


class _AnsiTextEdit(QTextEdit):
    """QTextEdit that can append lines containing ANSI SGR escape codes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapAnywhere)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        font = QFont("Menlo, Monaco, Courier New, monospace")
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self._cur_fg = QColor()
        self._cur_bg = QColor()
        self._cur_bold = False
        self._cur_italic = False

    def _make_char_fmt(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        if self._cur_fg.isValid():
            fmt.setForeground(self._cur_fg)
        if self._cur_bg.isValid():
            fmt.setBackground(self._cur_bg)
        fmt.setFontWeight(QFont.Bold if self._cur_bold else QFont.Normal)
        fmt.setFontItalic(self._cur_italic)
        return fmt

    def append_ansi_line(self, line: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        if not self.document().isEmpty():
            cursor.insertText("\n")
        # split with a capture group interleaves: [text, code, text, code, ...]
        parts = _ANSI_RE.split(line)
        for idx, part in enumerate(parts):
            if idx % 2 == 1:
                # odd indices are the captured SGR code strings
                params = [int(x) for x in part.split(";") if x.isdigit()]
                if not params:
                    params = [0]
                fg, bg, bold, italic = _fmt_from_sgr(params)
                if 0 in params:
                    self._cur_fg, self._cur_bg = fg, bg
                    self._cur_bold, self._cur_italic = bold, italic
                else:
                    if fg.isValid():
                        self._cur_fg = fg
                    if bg.isValid():
                        self._cur_bg = bg
                    if bold:
                        self._cur_bold = bold
                    if italic:
                        self._cur_italic = italic
            elif part:
                cursor.insertText(part, self._make_char_fmt())
        self.setTextCursor(cursor)
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def toPlainText(self) -> str:
        return self.document().toPlainText()


class _StdinLineEdit(QLineEdit):
    """QLineEdit that routes Up/Down to history callbacks instead of cursor movement."""

    def __init__(self, on_up, on_down, parent=None):
        super().__init__(parent)
        self._on_up = on_up
        self._on_down = on_down

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Up:
            self._on_up()
        elif event.key() == Qt.Key_Down:
            self._on_down()
        else:
            super().keyPressEvent(event)


class CommandPane(QWidget):
    def __init__(self, parent, handle: RunHandle, on_maximize, on_stop,
                 on_restart, on_remove=None, show_popout_btn=True, on_nickname=None,
                 on_change_worktree=None, worktrees=None, on_send=None,
                 on_unmaximize=None, confirm_fn=None):
        super().__init__(parent)
        self._handle = handle
        self._run_id = handle.run_id
        self._on_maximize = on_maximize
        self._on_unmaximize = on_unmaximize
        self._on_stop = on_stop
        self._on_restart = on_restart
        self._on_remove = on_remove
        self._show_popout_btn = show_popout_btn
        self._on_nickname = on_nickname
        self._on_change_worktree = on_change_worktree
        self._worktrees = worktrees or []
        self._status = handle.status
        self._on_send = on_send
        self._maximized = False
        self._confirm_fn = confirm_fn
        self._find_matches: list[int] = []
        self._find_cursor = 0
        self._find_query_len = 0
        self._stdin_history: list[str] = []
        self._stdin_history_pos: int = -1
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

        self._label = QLabel(
            f"{self._handle.cmd_name} · {self._handle.repo_name} :"
        )
        if self._on_nickname is not None:
            from PySide6.QtCore import Qt as _Qt
            self._label.setContextMenuPolicy(_Qt.CustomContextMenu)
            self._label.customContextMenuRequested.connect(self._show_nickname_menu)
        header.addWidget(self._label)

        self._wt_combo = FilterableComboBox()
        self._wt_combo.setToolTip("Switch worktree")
        self._populate_wt_combo()
        self._wt_combo.currentIndexChanged.connect(self._on_wt_combo_changed)
        header.addWidget(self._wt_combo, 1)

        if self._show_popout_btn:
            self._maximize_btn = self._mk_icon_btn(
                QStyle.SP_TitleBarMaxButton, "Maximize", self.trigger_maximize)
            header.addWidget(self._maximize_btn)
        header.addWidget(self._mk_icon_btn(
            QStyle.SP_BrowserReload, "Restart", self.trigger_restart))
        header.addWidget(self._mk_icon_btn(
            QStyle.SP_MediaStop, "Stop", self.trigger_stop))
        header.addWidget(self._mk_text_btn("Copy", "Copy output", self.trigger_copy))
        header.addWidget(self._mk_text_btn("Find", "Find in output", self.show_find_bar))
        header.addWidget(self._mk_icon_btn(
            QStyle.SP_TitleBarCloseButton, "Remove", self.trigger_remove))
        outer.addLayout(header)

        self._find_bar = QWidget()
        find_layout = QHBoxLayout(self._find_bar)
        find_layout.setContentsMargins(0, 0, 0, 0)
        self._find_entry = QLineEdit()
        self._find_entry.setPlaceholderText("Search…")
        self._find_entry.textChanged.connect(self._apply_find)
        self._find_entry.returnPressed.connect(self._find_next)
        find_layout.addWidget(self._find_entry, 1)
        self._find_count_label = QLabel("")
        self._find_count_label.setFixedWidth(80)
        find_layout.addWidget(self._find_count_label)
        find_layout.addWidget(self._mk_icon_btn(
            QStyle.SP_ArrowUp, "Previous match", self._find_prev))
        find_layout.addWidget(self._mk_icon_btn(
            QStyle.SP_ArrowDown, "Next match", self._find_next))
        find_layout.addWidget(self._mk_icon_btn(
            QStyle.SP_TitleBarCloseButton, "Close find bar", self.hide_find_bar))
        self._find_bar_visible = False
        self._find_bar.setVisible(False)
        outer.addWidget(self._find_bar)

        self._textbox = _AnsiTextEdit()
        self._textbox.setMinimumHeight(140)
        outer.addWidget(self._textbox, 1)

        # stdin input bar
        stdin_row = QHBoxLayout()
        stdin_row.setContentsMargins(0, 2, 0, 0)
        stdin_label = QLabel("stdin ›")
        stdin_row.addWidget(stdin_label)
        self._stdin_edit = _StdinLineEdit(self._on_history_up, self._on_history_down)
        self._stdin_edit.setPlaceholderText("stdin › type input and press Enter")
        self._stdin_edit.returnPressed.connect(self.trigger_send)
        stdin_row.addWidget(self._stdin_edit, 1)
        self._send_btn = QPushButton("Send")
        self._send_btn.setToolTip("Send input to process (Enter)")
        self._send_btn.clicked.connect(lambda _checked=False: self.trigger_send())
        stdin_row.addWidget(self._send_btn)
        outer.addLayout(stdin_row)

        self._set_stdin_enabled(self._status == RunStatus.RUNNING)

    def _mk_btn(self, label, handler):
        b = QPushButton(label)
        b.setFixedWidth(28)
        b.clicked.connect(lambda _checked=False: handler())
        return b

    def _mk_icon_btn(self, standard_pixmap, tooltip, handler):
        b = QPushButton()
        b.setIcon(self.style().standardIcon(standard_pixmap))
        b.setToolTip(tooltip)
        b.setFixedWidth(28)
        b.clicked.connect(lambda _checked=False: handler())
        return b

    def _mk_text_btn(self, label, tooltip, handler):
        b = QPushButton(label)
        b.setToolTip(tooltip)
        b.clicked.connect(lambda _checked=False: handler())
        return b

    def _show_nickname_menu(self, pos) -> None:
        wt_name = self._handle.worktree_path.split("/")[-1]
        menu = QMenu(self)
        menu.addAction("Add Nickname…").triggered.connect(
            lambda: self._on_nickname("run_command", {
                "repo": self._handle.repo_name,
                "worktree": wt_name,
                "cmd": self._handle.cmd_name,
            })
        )
        menu.exec(self._label.mapToGlobal(pos))

    def _populate_wt_combo(self) -> None:
        self._wt_combo.blockSignals(True)
        self._wt_combo.clear()
        current_path = self._handle.worktree_path
        selected = 0
        for i, wt in enumerate(self._worktrees):
            folder = wt.path.split("/")[-1]
            self._wt_combo.addItem(folder, userData=wt.path)
            if wt.path == current_path:
                selected = i
        self._wt_combo.setCurrentIndex(selected)
        self._wt_combo.blockSignals(False)

    def _on_wt_combo_changed(self, index: int) -> None:
        if index < 0 or self._on_change_worktree is None:
            return
        new_path = self._wt_combo.itemData(index)
        if new_path and new_path != self._handle.worktree_path:
            self._on_change_worktree(new_path)

    # --- public API ---

    def header_text(self) -> str:
        wt_folder = self._handle.worktree_path.split("/")[-1]
        return self._label.text() + " " + (self._wt_combo.currentText() or wt_folder)

    def append_line(self, line: str) -> None:
        self._textbox.append_ansi_line(line)
        if self._find_bar.isVisible():
            self._apply_find()

    def get_output_text(self) -> str:
        return self._textbox.toPlainText()

    def clear_output(self) -> None:
        self._textbox.clear()
        self._textbox._cur_fg = QColor()
        self._textbox._cur_bg = QColor()
        self._textbox._cur_bold = False
        self._textbox._cur_italic = False

    def set_status(self, status: RunStatus) -> None:
        self._status = status
        self._dot.setText(_STATUS_DOTS[status])
        self._dot.setStyleSheet(f"color: {_STATUS_COLORS[status]};")
        self._set_stdin_enabled(status == RunStatus.RUNNING)

    def status_dot_color(self) -> str:
        return _STATUS_COLORS[self._status]

    def update_run_id(self, run_id: str) -> None:
        self._run_id = run_id

    def update_callbacks(self, on_stop, on_restart, on_remove=None) -> None:
        self._on_stop = on_stop
        self._on_restart = on_restart
        if on_remove is not None:
            self._on_remove = on_remove

    def _confirm(self, message: str) -> bool:
        if self._confirm_fn is not None:
            return self._confirm_fn(message)
        return QMessageBox.question(
            self, "Confirm", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes

    def trigger_remove(self) -> None:
        if not self._on_remove:
            return
        if self._confirm(f'Remove "{self._handle.cmd_name}"?'):
            self._on_remove()

    def trigger_stop(self) -> None:
        self._on_stop()

    def trigger_restart(self) -> None:
        self._on_restart()

    def trigger_maximize(self) -> None:
        if self._maximized:
            self._maximized = False
            if self._show_popout_btn:
                self._maximize_btn.setToolTip("Maximize")
                self._maximize_btn.setIcon(
                    self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
            if self._on_unmaximize:
                self._on_unmaximize(self)
        else:
            self._maximized = True
            if self._show_popout_btn:
                self._maximize_btn.setToolTip("Unmaximize")
                self._maximize_btn.setIcon(
                    self.style().standardIcon(QStyle.SP_TitleBarNormalButton))
            self._on_maximize(self)

    def trigger_copy(self) -> None:
        QApplication.clipboard().setText(self.get_output_text())

    # --- stdin bar ---

    def stdin_bar_visible(self) -> bool:
        return True  # always visible; enabled state reflects process status

    def stdin_input_enabled(self) -> bool:
        return self._stdin_edit.isEnabled()

    def set_stdin_text(self, text: str) -> None:
        self._stdin_edit.setText(text)

    def get_stdin_text(self) -> str:
        return self._stdin_edit.text()

    def trigger_send(self) -> None:
        text = self._stdin_edit.text()
        if not text:
            return
        self._stdin_history.append(text)
        self._stdin_history_pos = -1
        self._stdin_edit.clear()
        if self._on_send:
            self._on_send(text)

    def _on_history_up(self) -> None:
        if not self._stdin_history:
            return
        if self._stdin_history_pos == -1:
            self._stdin_history_pos = len(self._stdin_history) - 1
        elif self._stdin_history_pos > 0:
            self._stdin_history_pos -= 1
        self._stdin_edit.setText(self._stdin_history[self._stdin_history_pos])

    def _on_history_down(self) -> None:
        if self._stdin_history_pos == -1:
            return
        if self._stdin_history_pos < len(self._stdin_history) - 1:
            self._stdin_history_pos += 1
            self._stdin_edit.setText(self._stdin_history[self._stdin_history_pos])
        else:
            self._stdin_history_pos = -1
            self._stdin_edit.clear()

    def _set_stdin_enabled(self, enabled: bool) -> None:
        self._stdin_edit.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

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
        self._find_query_len = len(query)
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
        self._render_find_highlights()
        return len(self._find_matches)

    # --- private ---

    def _render_find_highlights(self) -> None:
        doc = self._textbox.document()
        selections = []
        for i, pos in enumerate(self._find_matches):
            cursor = QTextCursor(doc)
            cursor.setPosition(pos)
            cursor.setPosition(pos + self._find_query_len, QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            if i == self._find_cursor:
                fmt.setBackground(QColor("orange"))
            else:
                fmt.setBackground(QColor("yellow"))
            fmt.setForeground(QColor("black"))
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            selections.append(sel)
        self._textbox.setExtraSelections(selections)

    def _update_find_count_label(self) -> None:
        total = len(self._find_matches)
        if not self._find_entry.text():
            self._find_count_label.setText("")
        elif total == 0:
            self._find_count_label.setText("0 matches")
        else:
            self._find_count_label.setText(f"{self._find_cursor + 1} of {total}")

    def _scroll_to_current_match(self) -> None:
        if not self._find_matches:
            return
        cursor = self._textbox.textCursor()
        cursor.setPosition(self._find_matches[self._find_cursor])
        self._textbox.setTextCursor(cursor)
        self._textbox.ensureCursorVisible()

    def _apply_find(self) -> None:
        query = self._find_entry.text() if self._find_bar.isVisible() else ""
        self.find(query)
        self._find_cursor = 0
        self._render_find_highlights()
        self._scroll_to_current_match()
        self._update_find_count_label()

    def _find_next(self) -> None:
        if not self._find_matches:
            return
        self._find_cursor = (self._find_cursor + 1) % len(self._find_matches)
        self._render_find_highlights()
        self._scroll_to_current_match()
        self._update_find_count_label()

    def _find_prev(self) -> None:
        if not self._find_matches:
            return
        self._find_cursor = (self._find_cursor - 1) % len(self._find_matches)
        self._render_find_highlights()
        self._scroll_to_current_match()
        self._update_find_count_label()
