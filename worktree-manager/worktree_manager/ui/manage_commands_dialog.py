from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from worktree_manager.ui.add_command_dialog import AddCommandDialog


class ManageCommandsDialog(QDialog):
    def __init__(self, parent, vm, initial_repo: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Manage Commands")
        self.setModal(True)
        self.resize(520, 480)
        self._vm = vm
        self._initial_repo = initial_repo
        self._editing_name: str | None = None
        self._action_buttons: list[QPushButton] = []
        self._done_btn: QPushButton | None = None
        self._edit_pattern_entry: QLineEdit | None = None
        self._build()

    def _build(self):
        repo_paths = list(self._vm.all_repos().keys())
        self._repo_map = {Path(p).name: p for p in repo_paths}
        display_names = list(self._repo_map.keys())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("Manage Commands")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        top.addWidget(title)
        top.addStretch(1)
        add_btn = QPushButton("+ Add Command")
        add_btn.clicked.connect(self._open_add_command_dialog)
        top.addWidget(add_btn)
        outer.addLayout(top)

        repo_row = QHBoxLayout()
        repo_row.addWidget(QLabel("Repository:"))
        explicit = self._initial_repo
        last_used = (
            self._vm.get_last_used_repo()
            if hasattr(self._vm, "get_last_used_repo") else None
        )
        if explicit and explicit in repo_paths:
            default_name = Path(explicit).name
        elif last_used and last_used in repo_paths:
            default_name = Path(last_used).name
        elif display_names:
            default_name = display_names[0]
        else:
            default_name = ""
        self._repo_combo = QComboBox()
        self._repo_combo.addItems(display_names)
        if default_name:
            self._repo_combo.setCurrentText(default_name)
        self._repo_combo.currentTextChanged.connect(self._on_repo_changed)
        repo_row.addWidget(self._repo_combo, 1)
        outer.addLayout(repo_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_container)
        outer.addWidget(self._scroll, 1)

        footer = QHBoxLayout()
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: gray;")
        footer.addWidget(self._count_label)
        footer.addStretch(1)
        self._done_btn = QPushButton("Done")
        self._done_btn.clicked.connect(self._on_done)
        footer.addWidget(self._done_btn)
        outer.addLayout(footer)

        if display_names:
            self._refresh_list()

    def _current_repo_path(self) -> str:
        return self._repo_map.get(self._repo_combo.currentText(), "")

    def _on_repo_changed(self, _: str) -> None:
        self._editing_name = None
        if hasattr(self._vm, "set_last_used_repo"):
            self._vm.set_last_used_repo(self._current_repo_path())
        self._refresh_list()

    def _refresh_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._action_buttons = []

        repo_path = self._current_repo_path()
        commands = self._vm.saved_commands(repo_path)
        n = len(commands)
        self._count_label.setText(
            f"{n} command{'s' if n != 1 else ''} saved for this repo"
        )

        if not commands:
            empty = QLabel(
                'No commands saved for this repo yet.\n'
                'Use "+ Add Command" in the toolbar to create one.'
            )
            empty.setStyleSheet("color: gray;")
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch(1)
            self._apply_lock_state()
            return

        for i, cmd in enumerate(commands):
            if i > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet("color: gray;")
                self._list_layout.addWidget(sep)
            if cmd.name == self._editing_name:
                self._list_layout.addWidget(self._build_edit_row(cmd.name, cmd.command, cmd.startup_pattern))
            else:
                self._list_layout.addWidget(self._build_view_row(cmd.name, cmd.command, cmd.startup_pattern))

        self._list_layout.addStretch(1)
        self._apply_lock_state()

    def _build_view_row(self, name: str, command: str, startup_pattern: str | None = None) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 4)

        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)
        cmd_label = QLabel(command)
        cmd_label.setStyleSheet("color: gray; font-size: 11px;")
        cmd_label.setWordWrap(True)
        layout.addWidget(cmd_label)
        if startup_pattern:
            pattern_label = QLabel(f"🚀 {startup_pattern}")
            pattern_label.setStyleSheet("color: gray; font-size: 10px;")
            layout.addWidget(pattern_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("background-color: #b04545; color: white;")
        del_btn.clicked.connect(lambda _c=False, n=name: self._delete(n))
        btn_row.addWidget(del_btn)
        copy_btn = QPushButton("⎘")
        copy_btn.setFixedWidth(36)
        copy_btn.clicked.connect(lambda _c=False, cmd=command: self._copy_command(cmd))
        btn_row.addWidget(copy_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda _c=False, n=name: self._start_edit(n))
        btn_row.addWidget(edit_btn)
        layout.addLayout(btn_row)

        self._action_buttons.extend([del_btn, copy_btn, edit_btn])
        return row

    def _build_edit_row(self, name: str, command: str, startup_pattern: str | None = None) -> QWidget:
        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)

        layout.addWidget(QLabel("Name"))
        name_entry = QLineEdit(name)
        layout.addWidget(name_entry)

        layout.addWidget(QLabel("Command"))
        cmd_text = QPlainTextEdit(command)
        cmd_text.setMinimumHeight(80)
        layout.addWidget(cmd_text)

        layout.addWidget(QLabel("Startup pattern (optional)"))
        self._edit_pattern_entry = QLineEdit(startup_pattern or "")
        self._edit_pattern_entry.setPlaceholderText("e.g. ready on — substring to detect server start")
        layout.addWidget(self._edit_pattern_entry)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._cancel_edit)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(
            lambda _c=False: self._save_edit(
                name, name_entry.text(), cmd_text.toPlainText(),
            )
        )
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        name_entry.setFocus()
        return row

    def _apply_lock_state(self) -> None:
        editing = self._editing_name is not None
        for btn in self._action_buttons:
            btn.setEnabled(not editing)
        if self._done_btn:
            self._done_btn.setEnabled(not editing)

    def _start_edit(self, name: str) -> None:
        self._editing_name = name
        self._refresh_list()

    def _cancel_edit(self) -> None:
        self._editing_name = None
        self._edit_pattern_entry = None
        self._refresh_list()

    def _save_edit(self, old_name: str, new_name: str, new_command: str) -> None:
        new_name = new_name.strip()
        new_command = new_command.strip()
        if not new_name or not new_command:
            return
        pattern = (self._edit_pattern_entry.text().strip() or None) if self._edit_pattern_entry else None
        repo_path = self._current_repo_path()
        if old_name != new_name:
            self._vm.delete_command(repo_path, old_name)
        self._vm.save_command(repo_path, new_name, new_command, startup_pattern=pattern)
        self._editing_name = None
        self._edit_pattern_entry = None
        self._refresh_list()

    def _delete(self, name: str) -> None:
        self._vm.delete_command(self._current_repo_path(), name)
        self._refresh_list()

    def _copy_command(self, command: str) -> None:
        QApplication.clipboard().setText(command)

    def _open_add_command_dialog(self) -> None:
        dlg = AddCommandDialog(
            parent=self, vm=self._vm,
            initial_repo=self._current_repo_path(),
            on_saved=self._refresh_list,
        )
        dlg.exec()

    def _on_done(self) -> None:
        if self._editing_name is not None:
            return
        self.accept()
