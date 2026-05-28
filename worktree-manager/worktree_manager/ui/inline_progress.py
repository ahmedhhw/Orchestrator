from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class InlineProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        self._message = QLabel()
        self._message.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._message)

        self._detail = QLabel()
        self._detail.setAlignment(Qt.AlignCenter)
        self._detail.setStyleSheet("color: gray; font-size: 11px;")
        self._detail.setVisible(False)
        layout.addWidget(self._detail)

        self._bar = QProgressBar()
        self._bar.setFixedWidth(300)
        layout.addWidget(self._bar, 0, Qt.AlignCenter)

    def start_indeterminate(self, message: str) -> None:
        self._message.setText(message)
        self._detail.setVisible(False)
        self._bar.setRange(0, 0)

    def start_determinate(self, message: str, total: int) -> None:
        self._message.setText(message)
        self._detail.setVisible(True)
        self._detail.setText("")
        self._bar.setRange(0, total)
        self._bar.setValue(0)

    def update(self, current: int, detail: str) -> None:
        self._bar.setValue(current)
        self._detail.setText(detail)
        self._detail.setVisible(True)

    def reset(self) -> None:
        self._bar.setRange(0, 1)
        self._bar.setValue(0)
        self._message.setText("")
        self._detail.setText("")
        self._detail.setVisible(False)
