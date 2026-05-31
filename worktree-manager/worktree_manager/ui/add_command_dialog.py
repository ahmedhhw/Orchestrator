from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from worktree_manager.ui.filterable_combo import FilterableComboBox


class AddCommandDialog(QDialog):
    def __init__(self, parent, vm, initial_repo: str | None = None, on_saved=None):
        super().__init__(parent)
        self.setWindowTitle("Add Saved Command")
        self.setModal(True)
        self._vm = vm
        self._on_saved = on_saved
        self._initial_repo = initial_repo
        self._build(initial_repo)

    def _build(self, initial_repo):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(8)

        title = QLabel("Add Saved Command")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        outer.addWidget(title)

        repo_paths = list(self._vm.all_repos().keys())
        self._repo_map = {Path(p).name: p for p in repo_paths}
        display_names = list(self._repo_map.keys())

        last_used = initial_repo or (
            self._vm.get_last_used_repo()
            if hasattr(self._vm, "get_last_used_repo") else None
        )
        if last_used and last_used in repo_paths:
            default_name = Path(last_used).name
        elif display_names:
            default_name = display_names[0]
        else:
            default_name = ""

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Repo:"))
        self._repo_combo = FilterableComboBox()
        self._repo_combo.addItems(display_names)
        if default_name:
            self._repo_combo.setCurrentText(default_name)
        self._repo_combo.setMinimumWidth(220)
        row1.addWidget(self._repo_combo, 1)
        outer.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Name:"))
        self._name_entry = QLineEdit()
        self._name_entry.setMinimumWidth(220)
        row2.addWidget(self._name_entry, 1)
        outer.addLayout(row2)

        outer.addWidget(QLabel("Command:"))
        self._cmd_text = QPlainTextEdit()
        self._cmd_text.setMinimumHeight(80)
        outer.addWidget(self._cmd_text)

        outer.addWidget(QLabel("Startup pattern (optional):"))
        self._pattern_entry = QLineEdit()
        self._pattern_entry.setPlaceholderText("e.g. ready on — substring to detect server start")
        outer.addWidget(self._pattern_entry)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        btns.addWidget(save)
        outer.addLayout(btns)

    def _save(self) -> None:
        name = self._name_entry.text().strip()
        cmd = self._cmd_text.toPlainText().strip()
        repo_name = self._repo_combo.currentText()
        repo_path = self._repo_map.get(repo_name, "")
        if not name or not cmd or not repo_path:
            return
        pattern = self._pattern_entry.text().strip() or None
        self._vm.save_command(repo_path, name, cmd, startup_pattern=pattern)
        if hasattr(self._vm, "set_last_used_repo"):
            self._vm.set_last_used_repo(repo_path)
        if self._on_saved:
            self._on_saved()
        self.accept()
