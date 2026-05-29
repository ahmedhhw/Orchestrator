from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette


_REMOVED_BG = "#3d0000"
_ADDED_BG   = "#003d00"
_HEADER_BG  = "#1e2a3a"


class DiffHunkView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_open_file_cb = None

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

    def set_hunks(self, path: str, hunks: list, live_mode: bool) -> None:
        self._file_label.setText(path)
        # Clear existing content (leave the stretch at end)
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        for hunk in hunks:
            self._add_hunk(hunk)

        # Open File button: always visible, disabled in read-only mode (this iteration)
        self._open_btn.setEnabled(False)

    def _add_hunk(self, hunk) -> None:
        # Hunk header label
        header_lbl = QLabel(hunk.header)
        header_lbl.setObjectName("hunk_header")
        header_lbl.setStyleSheet(f"background-color: {_HEADER_BG}; color: #aac4e0; padding: 2px 4px;")
        self._content_layout.insertWidget(self._content_layout.count() - 1, header_lbl)

        # Diff lines
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
            self._content_layout.insertWidget(self._content_layout.count() - 1, lbl)

    def _monospace_font(self):
        from PySide6.QtGui import QFont
        font = QFont("Menlo")
        if not font.exactMatch():
            font.setFamily("Courier New")
        font.setPointSize(11)
        return font

    def on_open_file(self, callback) -> None:
        self._on_open_file_cb = callback

    def _on_open_clicked(self) -> None:
        if self._on_open_file_cb:
            self._on_open_file_cb()
