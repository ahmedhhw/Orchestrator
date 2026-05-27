from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)


class BranchManagementPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # section tab strip
        tab_strip = QHBoxLayout()
        tab_strip.setContentsMargins(8, 8, 8, 0)
        tab_strip.setSpacing(4)

        self._sync_btn = QPushButton("Sync from origin")
        self._sync_btn.setCheckable(True)
        self._sync_btn.setChecked(True)
        self._sync_btn.clicked.connect(lambda: self._switch_section("sync"))
        tab_strip.addWidget(self._sync_btn)

        self._cleanup_btn = QPushButton("Cleanup")
        self._cleanup_btn.setCheckable(True)
        self._cleanup_btn.clicked.connect(lambda: self._switch_section("cleanup"))
        tab_strip.addWidget(self._cleanup_btn)

        tab_strip.addStretch(1)
        outer.addLayout(tab_strip)

        placeholder = QLabel(
            "Coming soon — Sync from origin and Cleanup will live here."
        )
        placeholder.setAlignment(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.AlignCenter)
        placeholder.setStyleSheet("color: gray; font-size: 14px;")
        placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(placeholder, 1)

    def _switch_section(self, section: str) -> None:
        self._sync_btn.setChecked(section == "sync")
        self._cleanup_btn.setChecked(section == "cleanup")
