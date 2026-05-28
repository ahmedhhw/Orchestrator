from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LandingScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(
            "Please select category from the left sidebar to get started."
        )
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: gray;")
        layout.addWidget(label)
