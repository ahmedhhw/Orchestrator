from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout,
)

from worktree_manager.setup_settings_vm import RepoSetupViewModel


class RepoSetupDialog(QDialog):
    def __init__(self, parent, vm: RepoSetupViewModel, on_confirm):
        super().__init__(parent)
        self.setWindowTitle("Worktree Storage")
        self.setModal(True)
        self._vm = vm
        self._on_confirm = on_confirm

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(8)

        title = QLabel("Where should worktrees be stored?")
        title.setStyleSheet("font-weight: bold;")
        outer.addWidget(title)

        row = QHBoxLayout()
        self._entry = QLineEdit(vm.default_storage_path())
        self._entry.setMinimumWidth(300)
        row.addWidget(self._entry, 1)
        browse = QPushButton("Browse")
        browse.setFixedWidth(80)
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        outer.addLayout(row)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        confirm = QPushButton("Confirm")
        confirm.clicked.connect(self._confirm)
        btns.addWidget(confirm)
        outer.addLayout(btns)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Choose worktree storage folder",
        )
        if path:
            self._entry.setText(path)

    def _confirm(self):
        self._vm.confirm(storage_path=self._entry.text(), callback=self._on_confirm)
        self.accept()
