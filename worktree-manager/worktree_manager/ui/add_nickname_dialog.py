from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)


class AddNicknameDialog(QDialog):
    def __init__(self, parent, reserved_keywords: list[str], existing_nicknames: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Add Nickname")
        self.setModal(True)
        self._reserved = set(kw.lower() for kw in reserved_keywords)
        self._existing = set(existing_nicknames)
        self._nickname: str = ""
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(8)

        outer.addWidget(QLabel("Nickname (single word):"))
        self._entry = QLineEdit()
        self._entry.setPlaceholderText("e.g. myserver")
        self._entry.returnPressed.connect(self._on_save)
        outer.addWidget(self._entry)

        self._error = QLabel("")
        self._error.setStyleSheet("color: red;")
        self._error.hide()
        outer.addWidget(self._error)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        save = QPushButton("Save")
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        btns.addWidget(save)
        outer.addLayout(btns)

    def _on_save(self) -> None:
        nick = self._entry.text().strip()
        if not nick:
            self._show_error("Nickname cannot be empty.")
            return
        if " " in nick:
            self._show_error("Nickname must be a single word (no spaces).")
            return
        if nick.lower() in self._reserved:
            self._show_error(f'"{nick}" is a built-in keyword and cannot be used.')
            return
        self._nickname = nick
        self.accept()

    def _show_error(self, msg: str) -> None:
        self._error.setText(msg)
        self._error.show()

    def nickname(self) -> str:
        return self._nickname
