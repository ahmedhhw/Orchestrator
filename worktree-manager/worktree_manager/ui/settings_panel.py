from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout,
)

from worktree_manager.setup_settings_vm import SettingsViewModel


class SettingsDialog(QDialog):
    def __init__(self, parent, vm: SettingsViewModel, store=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self._vm = vm
        self._store = store

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(8)

        title = QLabel("Settings")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        outer.addWidget(title)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Worktree storage:"))
        self._storage_entry = QLineEdit(vm.worktree_storage)
        self._storage_entry.setMinimumWidth(240)
        row1.addWidget(self._storage_entry, 1)
        browse = QPushButton("Browse")
        browse.setFixedWidth(80)
        browse.clicked.connect(self._browse)
        row1.addWidget(browse)
        outer.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Stale threshold:"))
        self._stale_spin = QSpinBox()
        self._stale_spin.setRange(1, 3650)
        self._stale_spin.setValue(int(vm.stale_days))
        row2.addWidget(self._stale_spin)
        row2.addWidget(QLabel("days"))
        row2.addStretch(1)
        outer.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Shell:"))
        self._shell_combo = QComboBox()
        self._shell_combo.addItems(["zsh", "bash"])
        current_shell = store.get_ui_pref("shell", "zsh") if store else "zsh"
        idx = self._shell_combo.findText(current_shell)
        self._shell_combo.setCurrentIndex(idx if idx >= 0 else 0)
        row3.addWidget(self._shell_combo)
        row3.addStretch(1)
        outer.addLayout(row3)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        btns.addWidget(save)
        outer.addLayout(btns)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Choose worktree storage")
        if path:
            self._storage_entry.setText(path)

    def _save(self):
        self._vm.save(
            worktree_storage=self._storage_entry.text(),
            stale_days=int(self._stale_spin.value()),
        )
        if self._store:
            self._store.set_ui_pref("shell", self._shell_combo.currentText())
        self.accept()
