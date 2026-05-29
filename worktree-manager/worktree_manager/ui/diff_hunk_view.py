from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QCheckBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


_REMOVED_BG = "#3d0000"
_ADDED_BG   = "#003d00"
_HEADER_BG  = "#1e2a3a"


class DiffHunkView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_open_file_cb = None
        self._on_restore_cb = None
        self._hunk_checkboxes = []  # list of (hunk_index, QCheckBox)
        self._restore_btn = None
        self._toast_timer = None
        self._undo_callback = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # File header bar
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(8, 4, 8, 4)
        self._file_label = QLabel("")
        self._file_label.setObjectName("diff_file_label")
        header_bar.addWidget(self._file_label, 1)
        self._open_btn = QPushButton("↗ Open File")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open_clicked)
        header_bar.addWidget(self._open_btn)
        outer.addLayout(header_bar)

        # Scrollable hunk content area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 4, 8, 4)
        self._content_layout.setSpacing(0)
        self._content_layout.addStretch(1)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)

        # Action bar (select all/none + restore) — hidden until live mode
        self._action_bar = QWidget()
        action_layout = QHBoxLayout(self._action_bar)
        action_layout.setContentsMargins(8, 4, 8, 4)
        self._all_btn = QPushButton("☑ All")
        self._all_btn.clicked.connect(self._select_all)
        action_layout.addWidget(self._all_btn)
        self._none_btn = QPushButton("☐ None")
        self._none_btn.clicked.connect(self._select_none)
        action_layout.addWidget(self._none_btn)
        action_layout.addStretch(1)
        self._restore_btn = QPushButton("Restore 0 hunks → FROM")
        self._restore_btn.clicked.connect(self._on_restore_clicked)
        action_layout.addWidget(self._restore_btn)
        self._action_bar.hide()
        outer.addWidget(self._action_bar)

        # Toast area
        self._toast_container = QWidget()
        toast_layout = QHBoxLayout(self._toast_container)
        toast_layout.setContentsMargins(8, 4, 8, 4)
        self._toast_label = QLabel("")
        toast_layout.addWidget(self._toast_label, 1)
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.clicked.connect(self._on_undo_clicked)
        toast_layout.addWidget(self._undo_btn)
        self._toast_container.hide()
        outer.addWidget(self._toast_container)

    def set_hunks(self, path: str, hunks: list, live_mode: bool) -> None:
        self._file_label.setText(path)
        self._hunk_checkboxes.clear()

        # Clear existing content (leave the stretch at end)
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        for hunk in hunks:
            self._add_hunk(hunk, live_mode=live_mode)

        self._open_btn.setEnabled(live_mode)

        if live_mode:
            self._action_bar.show()
            self._update_restore_button()
        else:
            self._action_bar.hide()

    def _add_hunk(self, hunk, live_mode: bool) -> None:
        pos = self._content_layout.count() - 1  # insert before stretch

        if live_mode:
            row = QHBoxLayout()
            cb = QCheckBox()
            cb.stateChanged.connect(self._update_restore_button)
            row.addWidget(cb)
            self._hunk_checkboxes.append((hunk.index, cb))

            header_lbl = QLabel(hunk.header)
            header_lbl.setObjectName("hunk_header")
            header_lbl.setStyleSheet(
                f"background-color: {_HEADER_BG}; color: #aac4e0; padding: 2px 4px;"
            )
            row.addWidget(header_lbl, 1)

            container = QWidget()
            container.setLayout(row)
            self._content_layout.insertWidget(pos, container)
            pos += 1
        else:
            header_lbl = QLabel(hunk.header)
            header_lbl.setObjectName("hunk_header")
            header_lbl.setStyleSheet(
                f"background-color: {_HEADER_BG}; color: #aac4e0; padding: 2px 4px;"
            )
            self._content_layout.insertWidget(pos, header_lbl)
            pos += 1

        for line in hunk.lines:
            lbl = QLabel(line if line else " ")
            lbl.setObjectName("diff_line")
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lbl.setFont(self._monospace_font())
            if line.startswith("-"):
                lbl.setStyleSheet(f"background-color: {_REMOVED_BG}; color: #ff8080; padding: 0 4px;")
            elif line.startswith("+"):
                lbl.setStyleSheet(f"background-color: {_ADDED_BG}; color: #80ff80; padding: 0 4px;")
            else:
                lbl.setStyleSheet("padding: 0 4px;")
            self._content_layout.insertWidget(pos, lbl)
            pos += 1

    def _select_all(self) -> None:
        for _, cb in self._hunk_checkboxes:
            cb.setChecked(True)

    def _select_none(self) -> None:
        for _, cb in self._hunk_checkboxes:
            cb.setChecked(False)

    def _update_restore_button(self) -> None:
        if self._restore_btn is None:
            return
        count = sum(1 for _, cb in self._hunk_checkboxes if cb.isChecked())
        label = "hunk" if count == 1 else "hunks"
        self._restore_btn.setText(f"Restore {count} {label} → FROM")

    def _on_restore_clicked(self) -> None:
        if self._on_restore_cb is None:
            return
        indices = [idx for idx, cb in self._hunk_checkboxes if cb.isChecked()]
        self._on_restore_cb(indices)

    def on_restore(self, callback) -> None:
        self._on_restore_cb = callback

    def on_open_file(self, callback) -> None:
        self._on_open_file_cb = callback

    def _on_open_clicked(self) -> None:
        if self._on_open_file_cb:
            self._on_open_file_cb()

    def show_toast(self, message: str, undo_cb) -> None:
        if self._toast_timer is not None:
            self._toast_timer.stop()
            self._toast_timer = None

        self._toast_label.setText(message)
        self._undo_callback = undo_cb

        if undo_cb is not None:
            self._undo_btn.show()
        else:
            self._undo_btn.hide()

        self._toast_container.show()

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.dismiss_toast)
        self._toast_timer.start(8000)

    def dismiss_toast(self) -> None:
        self._toast_container.hide()
        self._toast_label.setText("")
        self._undo_callback = None
        if self._toast_timer is not None:
            self._toast_timer.stop()
            self._toast_timer = None

    def _on_undo_clicked(self) -> None:
        cb = self._undo_callback
        self.dismiss_toast()
        if cb:
            cb()

    def _monospace_font(self):
        font = QFont("Menlo")
        if not font.exactMatch():
            font.setFamily("Courier New")
        font.setPointSize(11)
        return font
