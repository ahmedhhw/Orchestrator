from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LandingScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(
            "No repo selected.\n"
            "Pick one from the sidebar or click + Add Repo."
        )
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: gray;")
        layout.addWidget(label)
