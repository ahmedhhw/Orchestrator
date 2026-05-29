from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QSizePolicy, QVBoxLayout, QWidget


class SidebarStrip(QWidget):
    def __init__(self, on_restore, parent=None):
        super().__init__(parent)
        self.setFixedWidth(24)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        btn = QPushButton("▶")
        btn.setFixedWidth(24)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        btn.setStyleSheet(
            "QPushButton {"
            "  border: none;"
            "  background-color: #e8e8e8;"
            "  color: #555;"
            "  font-size: 10px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #d0d0d0;"
            "}"
        )
        btn.clicked.connect(on_restore)
        layout.addWidget(btn)
