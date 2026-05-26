from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)


class SpotlightConfirmDialog(QDialog):
    def __init__(
        self,
        parent,
        title: str,
        message: str,
        show_also_branch: bool = False,
        branch_protected: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._also_branch_cb: QCheckBox | None = None
        self._build(message, show_also_branch, branch_protected)

    def _build(self, message: str, show_also_branch: bool, branch_protected: bool) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(10)

        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        outer.addWidget(msg)

        if show_also_branch:
            cb_text = "Also delete branch  (protected)" if branch_protected else "Also delete branch"
            self._also_branch_cb = QCheckBox(cb_text)
            self._also_branch_cb.setChecked(not branch_protected)
            if branch_protected:
                self._also_branch_cb.setEnabled(False)
            outer.addWidget(self._also_branch_cb)

        btns = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self._cancel_btn)
        btns.addStretch(1)
        self._confirm_btn = QPushButton("Delete")
        self._confirm_btn.setStyleSheet("background-color: #c0392b; color: white;")
        self._confirm_btn.clicked.connect(self.accept)
        btns.addWidget(self._confirm_btn)
        outer.addLayout(btns)

    def also_delete_branch(self) -> bool:
        if self._also_branch_cb is None:
            return False
        return self._also_branch_cb.isChecked()
