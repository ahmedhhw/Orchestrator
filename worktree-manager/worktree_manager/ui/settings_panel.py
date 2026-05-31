from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout,
)

from worktree_manager.ui.filterable_combo import FilterableComboBox

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
        self._shell_combo = FilterableComboBox()
        self._shell_combo.addItems(["zsh", "bash"])
        current_shell = store.get_ui_pref("shell", "zsh") if store else "zsh"
        idx = self._shell_combo.findText(current_shell)
        self._shell_combo.setCurrentIndex(idx if idx >= 0 else 0)
        row3.addWidget(self._shell_combo)
        row3.addStretch(1)
        outer.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Default editor:"))
        self._editor_combo = FilterableComboBox()
        self._editor_combo.addItem("Cursor", userData="cursor")
        self._editor_combo.addItem("VS Code", userData="vscode")
        current_editor = store.get_ui_pref("editor", "cursor") if store else "cursor"
        editor_idx = self._editor_combo.findData(current_editor)
        self._editor_combo.setCurrentIndex(editor_idx if editor_idx >= 0 else 0)
        row4.addWidget(self._editor_combo)
        row4.addStretch(1)
        outer.addLayout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Branch diff mode:"))
        self._branch_diff_combo = FilterableComboBox()
        self._branch_diff_combo.addItem("Merge base (default)", userData="merge_base")
        self._branch_diff_combo.addItem("Branch tip", userData="branch_tip")
        current_mode = store.get_branch_diff_mode() if store else "merge_base"
        mode_idx = self._branch_diff_combo.findData(current_mode)
        self._branch_diff_combo.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
        row5.addWidget(self._branch_diff_combo)
        row5.addStretch(1)
        outer.addLayout(row5)

        row6 = QHBoxLayout()
        row6.addWidget(QLabel("GitHub polling:"))
        self._github_poll_spin = QSpinBox()
        self._github_poll_spin.setRange(5, 3600)
        current_poll = store.get_github_poll_interval() if store else 30
        self._github_poll_spin.setValue(current_poll)
        row6.addWidget(self._github_poll_spin)
        row6.addWidget(QLabel("seconds"))
        row6.addStretch(1)
        outer.addLayout(row6)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save)
        btns.addWidget(self._save_btn)
        outer.addLayout(btns)

    def _save(self):
        self._vm.save(
            worktree_storage=self._vm.worktree_storage,
            stale_days=int(self._stale_spin.value()),
        )
        if self._store:
            self._store.set_ui_pref("shell", self._shell_combo.currentText())
            self._store.set_ui_pref("editor", self._editor_combo.currentData())
            self._store.set_branch_diff_mode(self._branch_diff_combo.currentData())
            self._store.save_github_poll_interval(int(self._github_poll_spin.value()))
        self.accept()
