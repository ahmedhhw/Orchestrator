from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)


class QuickLaunchDialog(QDialog):
    def __init__(self, parent, worktree_path: str, on_run):
        super().__init__(parent)
        self.setWindowTitle("Run Command")
        self.setModal(True)
        self._worktree_path = worktree_path
        self._on_run = on_run
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(8)

        wt_row = QHBoxLayout()
        wt_row.addWidget(QLabel("Worktree:"))
        wt_label = QLabel(self._worktree_path)
        wt_label.setStyleSheet("color: gray;")
        wt_row.addWidget(wt_label, 1)
        outer.addLayout(wt_row)

        cmd_row = QHBoxLayout()
        cmd_row.addWidget(QLabel("Command:"))
        self._cmd_input = QLineEdit()
        self._cmd_input.setPlaceholderText("e.g. echo $(git log --oneline -5)")
        cmd_row.addWidget(self._cmd_input, 1)
        outer.addLayout(cmd_row)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        run_btn = QPushButton("Run")
        run_btn.setDefault(True)
        run_btn.clicked.connect(self.trigger_run)
        btns.addWidget(run_btn)
        outer.addLayout(btns)

    def trigger_run(self):
        cmd = self._cmd_input.text().strip()
        if not cmd:
            return
        self._on_run(cmd)
        self.accept()
