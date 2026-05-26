from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
    QWidget,
)

from worktree_manager.command_runner import RunStatus
from worktree_manager.models import SavedCommand, WorktreeModel


class _EditCommandDialog(QDialog):
    def __init__(self, parent, cmd: SavedCommand, on_save):
        super().__init__(parent)
        self.setWindowTitle("Edit Command")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._cmd = cmd
        self._on_save = on_save
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(8)

        outer.addWidget(QLabel("Name"))
        self._name_entry = QLineEdit(self._cmd.name)
        outer.addWidget(self._name_entry)

        outer.addWidget(QLabel("Command"))
        self._cmd_text = QPlainTextEdit(self._cmd.command)
        self._cmd_text.setMinimumHeight(80)
        outer.addWidget(self._cmd_text)

        outer.addWidget(QLabel("Startup pattern (optional)"))
        self._pattern_entry = QLineEdit(self._cmd.startup_pattern or "")
        self._pattern_entry.setPlaceholderText("e.g. ready on — substring to detect server start")
        outer.addWidget(self._pattern_entry)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        outer.addLayout(btn_row)

        self._name_entry.setFocus()

    def _save(self):
        name = self._name_entry.text().strip()
        command = self._cmd_text.toPlainText().strip()
        if not name or not command:
            return
        pattern = self._pattern_entry.text().strip() or None
        self._on_save(self._cmd.name, name, command, pattern)
        self.accept()


class _CmdRowButton(QPushButton):
    def __init__(self, cmd: SavedCommand, on_click, on_double_click, on_right_click):
        display = f"{cmd.name}   —   {cmd.command}".replace("&", "&&")
        super().__init__(display)
        self.cmd = cmd
        self._on_click = on_click
        self._on_double_click = on_double_click
        self._on_right_click = on_right_click
        self.setStyleSheet("text-align: left; padding: 6px;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self._on_right_click(self.cmd, self.mapToGlobal(pos))
        )
        self.clicked.connect(lambda _c=False: self._on_click(self.cmd))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_double_click(self.cmd)
        else:
            super().mouseDoubleClickEvent(event)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                "text-align: left; padding: 6px;"
                " background-color: #4a90d9; color: white;"
            )
        else:
            self.setStyleSheet("text-align: left; padding: 6px;")


class _TrackableButton(QPushButton):
    """QPushButton that reports its intended visibility even before the parent is shown."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shown = True

    def set_shown(self, value: bool) -> None:
        self._shown = value
        self.setVisible(value)

    def isVisible(self) -> bool:
        return self._shown


class LaunchDialog(QDialog):
    def __init__(self, parent, vm,
                 locked_repo_path: str | None = None,
                 locked_worktree_path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Launch Command")
        self.setModal(True)
        self._vm = vm
        self._locked_repo_path = locked_repo_path
        self._locked_worktree_path = locked_worktree_path
        self._commands: list[SavedCommand] = []
        self._worktrees: list[WorktreeModel] = []
        self._selected_cmd: SavedCommand | None = None
        self._cmd_row_widgets: list[_CmdRowButton] = []
        self._conflict_run_id: str | None = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(6)

        title = QLabel("Launch Command")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        outer.addWidget(title)

        repo_paths = list(self._vm.all_repos().keys())
        self._repo_map = {Path(p).name: p for p in repo_paths}
        display_names = list(self._repo_map.keys())

        if self._locked_repo_path:
            default_name = Path(self._locked_repo_path).name
        else:
            last_used = (
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
        self._repo_combo = QComboBox()
        self._repo_combo.addItems(display_names)
        if default_name:
            self._repo_combo.setCurrentText(default_name)
        self._repo_combo.currentTextChanged.connect(self._on_repo_changed)
        self._repo_combo.setMinimumWidth(200)
        if self._locked_repo_path:
            self._repo_combo.setEnabled(False)
        row1.addWidget(self._repo_combo, 1)
        outer.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Worktree:"))
        self._wt_combo = QComboBox()
        self._wt_combo.setMinimumWidth(200)
        if self._locked_worktree_path:
            self._wt_combo.setEnabled(False)
        row2.addWidget(self._wt_combo, 1)
        outer.addLayout(row2)

        cmd_row = QHBoxLayout()
        cmd_row.addWidget(QLabel("Saved commands:"))
        cmd_row.addStretch(1)
        self._cmd_filter = QLineEdit()
        self._cmd_filter.setPlaceholderText("Filter…")
        self._cmd_filter.setFixedWidth(160)
        self._cmd_filter.textChanged.connect(self._render_cmd_list)
        cmd_row.addWidget(self._cmd_filter)
        outer.addLayout(cmd_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(140)
        self._cmd_container = QWidget()
        self._cmd_layout = QVBoxLayout(self._cmd_container)
        self._cmd_layout.setContentsMargins(0, 0, 0, 0)
        self._cmd_layout.setSpacing(1)
        self._cmd_layout.addStretch(1)
        self._scroll.setWidget(self._cmd_container)
        outer.addWidget(self._scroll, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(sep)

        outer.addWidget(QLabel("Command to run:"))

        # Banner: shown when name field matches a saved command
        banner_row = QHBoxLayout()
        self._banner_label = QLabel("")
        self._banner_label.setStyleSheet("color: #888;")
        banner_row.addWidget(self._banner_label, 1)
        self._banner_action_btn = QPushButton("")
        self._banner_action_btn.setVisible(False)
        self._banner_action_btn.clicked.connect(self._on_banner_action)
        banner_row.addWidget(self._banner_action_btn)
        self._banner_widget = QWidget()
        self._banner_widget.setLayout(banner_row)
        self._banner_widget.setVisible(False)
        outer.addWidget(self._banner_widget)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self._name_entry = QLineEdit()
        self._name_entry.setPlaceholderText("Optional — fill to save")
        self._name_entry.textChanged.connect(self._on_fields_changed)
        name_row.addWidget(self._name_entry, 1)
        outer.addLayout(name_row)

        self._name_collision_label = QLabel("")
        self._name_collision_label.setStyleSheet("color: #c8922a; font-size: 11px;")
        self._name_collision_label.setVisible(False)
        outer.addWidget(self._name_collision_label)

        self._cmd_edit = QPlainTextEdit()
        self._cmd_edit.setPlaceholderText("Pick a saved command above, or type one here…")
        self._cmd_edit.setMinimumHeight(60)
        self._cmd_edit.setMaximumHeight(100)
        self._cmd_edit.textChanged.connect(self._on_fields_changed)
        outer.addWidget(self._cmd_edit)

        self._conflict_label = QLabel("")
        self._conflict_label.setStyleSheet("color: red;")
        self._conflict_label.setWordWrap(True)
        outer.addWidget(self._conflict_label)
        self._restart_btn = _TrackableButton("Restart")
        self._restart_btn.setFixedWidth(80)
        self._restart_btn.clicked.connect(self._trigger_conflict_restart)
        self._restart_btn.set_shown(False)
        outer.addWidget(self._restart_btn)

        footer = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._trigger_save)
        footer.addWidget(self._save_btn)
        footer.addStretch(1)
        self._run_btn = QPushButton("Run ▶")
        self._run_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._run_btn.clicked.connect(self.trigger_run)
        footer.addWidget(self._run_btn)
        outer.addLayout(footer)

        if self._locked_repo_path:
            self._on_repo_changed(Path(self._locked_repo_path).name)
        elif default_name:
            self._on_repo_changed(default_name)

    # ── repo / worktree ────────────────────────────────────────────────────────

    def _on_repo_changed(self, repo_name: str) -> None:
        repo_path = self._locked_repo_path or self._repo_map.get(repo_name, "")
        self._commands = self._vm.saved_commands(repo_path)
        self._selected_cmd = None
        self._cmd_filter.blockSignals(True)
        self._cmd_filter.setText("")
        self._cmd_filter.blockSignals(False)
        self._worktrees = self._vm.list_worktrees(repo_path)
        wt_labels = [f"{wt.branch}  ({wt.path})" for wt in self._worktrees]
        self._wt_combo.clear()
        self._wt_combo.addItems(wt_labels)
        if self._locked_worktree_path:
            for i, wt in enumerate(self._worktrees):
                if wt.path == self._locked_worktree_path:
                    self._wt_combo.setCurrentIndex(i)
                    break
        self._render_cmd_list()

    def _current_repo_path(self) -> str:
        if self._locked_repo_path:
            return self._locked_repo_path
        return self._repo_map.get(self._repo_combo.currentText(), "")

    def _current_worktree_path(self) -> str:
        if self._locked_worktree_path:
            return self._locked_worktree_path
        idx = self._wt_combo.currentIndex()
        if 0 <= idx < len(self._worktrees):
            return self._worktrees[idx].path
        return ""

    # ── saved command list ─────────────────────────────────────────────────────

    def _visible_cmds(self) -> list[SavedCommand]:
        term = self._cmd_filter.text().strip().lower()
        return [
            c for c in self._commands
            if not term or term in c.name.lower() or term in c.command.lower()
        ]

    def _render_cmd_list(self) -> None:
        while self._cmd_layout.count():
            item = self._cmd_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._cmd_row_widgets = []

        visible = self._visible_cmds()
        if not visible:
            empty = QLabel("No saved commands for this repo.")
            empty.setStyleSheet("color: gray;")
            self._cmd_layout.addWidget(empty)
            self._cmd_layout.addStretch(1)
            return

        for cmd in visible:
            row = _CmdRowButton(cmd,
                on_click=self._fill_from_saved,
                on_double_click=self._run_saved_immediately,
                on_right_click=self._show_cmd_context_menu,
            )
            self._cmd_layout.addWidget(row)
            self._cmd_row_widgets.append(row)

        self._cmd_layout.addStretch(1)

    def _highlight_row(self, cmd: SavedCommand | None) -> None:
        for row in self._cmd_row_widgets:
            row.set_selected(cmd is not None and row.cmd is cmd)

    def _cmd_for_name(self, name: str) -> SavedCommand | None:
        return next((c for c in self._commands if c.name == name), None)

    # ── fill textarea from saved command ──────────────────────────────────────

    def _fill_from_saved(self, cmd: SavedCommand) -> None:
        self._selected_cmd = cmd
        self._cmd_edit.blockSignals(True)
        self._name_entry.blockSignals(True)
        self._cmd_edit.setPlainText(cmd.command)
        self._name_entry.setText(cmd.name)
        self._cmd_edit.blockSignals(False)
        self._name_entry.blockSignals(False)
        self._highlight_row(cmd)
        self._on_fields_changed()

    # ── reactive field updates ────────────────────────────────────────────────

    def _on_fields_changed(self) -> None:
        name = self._name_entry.text().strip()
        cmd_text = self._cmd_edit.toPlainText().strip()
        saved = self._cmd_for_name(name)

        # Banner
        if saved:
            if cmd_text == saved.command:
                self._banner_label.setText(f'⊙ From saved: "{name}"')
                self._banner_action_btn.setText("Clear")
                self._banner_action_btn.setProperty("_action", "clear")
            else:
                self._banner_label.setText(f'⊙ Modified from "{name}"')
                self._banner_action_btn.setText("Revert")
                self._banner_action_btn.setProperty("_action", "revert")
            self._banner_action_btn.setVisible(True)
            self._banner_widget.setVisible(True)
        else:
            self._banner_widget.setVisible(False)

        # Collision warning: only when name matches a saved command AND body differs
        if saved and cmd_text and cmd_text != saved.command:
            self._name_collision_label.setText(f'⚠ Will overwrite existing "{name}"')
            self._name_collision_label.setVisible(True)
        else:
            self._name_collision_label.setVisible(False)

        # Save button visibility
        self._save_btn.setVisible(bool(cmd_text))

    def _on_banner_action(self) -> None:
        name = self._name_entry.text().strip()
        if self._banner_action_btn.property("_action") == "revert":
            saved = self._cmd_for_name(name)
            if saved:
                self._cmd_edit.blockSignals(True)
                self._cmd_edit.setPlainText(saved.command)
                self._cmd_edit.blockSignals(False)
                self._on_fields_changed()
        else:
            self._cmd_edit.clear()
            self._name_entry.clear()
            self._selected_cmd = None
            self._highlight_row(None)
            self._on_fields_changed()

    # ── edit / delete / copy ──────────────────────────────────────────────────

    def _open_edit_dialog(self, cmd: SavedCommand) -> None:
        def on_save(old_name, new_name, new_command, pattern):
            repo_path = self._current_repo_path()
            if old_name != new_name:
                self._vm.delete_command(repo_path, old_name)
            self._vm.save_command(repo_path, new_name, new_command, startup_pattern=pattern)
            self._on_repo_changed(Path(repo_path).name)
        dlg = _EditCommandDialog(parent=self, cmd=cmd, on_save=on_save)
        dlg.exec()

    def _show_cmd_context_menu(self, cmd: SavedCommand, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit…").triggered.connect(lambda: self._open_edit_dialog(cmd))
        menu.addAction("Copy command").triggered.connect(
            lambda: QApplication.clipboard().setText(cmd.command)
        )
        menu.addAction("Delete").triggered.connect(lambda: self._delete_cmd(cmd))
        menu.exec(pos)

    def _delete_cmd(self, cmd: SavedCommand) -> None:
        repo_path = self._current_repo_path()
        self._vm.delete_command(repo_path, cmd.name)
        if self._selected_cmd is cmd:
            self._selected_cmd = None
        self._on_repo_changed(Path(repo_path).name)

    # ── run / save ────────────────────────────────────────────────────────────

    def trigger_run(self) -> None:
        cmd_text = self._cmd_edit.toPlainText().strip()
        if not cmd_text:
            return

        repo_path = self._current_repo_path()
        worktree_path = self._current_worktree_path()
        repo_name = Path(repo_path).name
        name = self._name_entry.text().strip()
        saved = self._cmd_for_name(name)

        if saved and cmd_text == saved.command:
            # Running a saved command unchanged — check for conflicts
            existing = None
            if hasattr(self._vm, "find_existing_run"):
                existing = self._vm.find_existing_run(name, repo_path, worktree_path)
            if existing is not None:
                if existing.status == RunStatus.RUNNING:
                    self._show_conflict(
                        f'"{name}" is already running in this worktree.',
                        show_restart=False, run_id=None,
                    )
                else:
                    self._show_conflict(
                        f'"{name}" already exists but is stopped. Restart it?',
                        show_restart=True, run_id=existing.run_id,
                    )
                return
            cmd_name = name
            startup_pattern = getattr(saved, "startup_pattern", None)
        else:
            cmd_name = name or "[one-off]"
            startup_pattern = None

        self._vm.launch(
            repo_path=repo_path, repo_name=repo_name,
            cmd_name=cmd_name, command_str=cmd_text,
            worktree_path=worktree_path,
            startup_pattern=startup_pattern,
        )
        if hasattr(self._vm, "set_last_used_repo"):
            self._vm.set_last_used_repo(repo_path)
        self.accept()

    def _run_saved_immediately(self, cmd: SavedCommand) -> None:
        self._fill_from_saved(cmd)
        self.trigger_run()

    def _trigger_save(self) -> None:
        name = self._name_entry.text().strip()
        cmd_text = self._cmd_edit.toPlainText().strip()
        if not cmd_text or not name:
            return
        repo_path = self._current_repo_path()
        self._vm.save_command(repo_path, name, cmd_text)
        self._on_repo_changed(Path(repo_path).name)

    def _show_conflict(self, message: str, show_restart: bool,
                       run_id: str | None) -> None:
        self._conflict_label.setText(message)
        self._conflict_run_id = run_id
        self._restart_btn.set_shown(show_restart)

    def _trigger_conflict_restart(self) -> None:
        if self._conflict_run_id and hasattr(self._vm, "restart"):
            self._vm.restart(self._conflict_run_id)
        self.accept()

    # ── public API for tests ──────────────────────────────────────────────────

    def command_choices(self) -> list[str]:
        return [c.name for c in self._commands]

    def worktree_choices(self) -> list[str]:
        return [f"{wt.branch}  ({wt.path})" for wt in self._worktrees]

    def set_command(self, name: str) -> None:
        for cmd in self._commands:
            if cmd.name == name:
                self._fill_from_saved(cmd)
                return

    def set_worktree(self, path: str) -> None:
        for i, wt in enumerate(self._worktrees):
            if wt.path == path:
                self._wt_combo.setCurrentIndex(i)
                return

    def trigger_launch(self) -> None:
        self.trigger_run()

    def set_run_once_text(self, text: str) -> None:
        self._cmd_edit.blockSignals(True)
        self._cmd_edit.setPlainText(text)
        self._cmd_edit.blockSignals(False)
        self._on_fields_changed()

    def set_run_once_name(self, name: str) -> None:
        self._name_entry.setText(name)

    def trigger_run_once(self) -> None:
        self.trigger_run()

    def trigger_save_run_once(self, name: str) -> None:
        cmd_text = self._cmd_edit.toPlainText().strip()
        if not cmd_text or not name:
            return
        repo_path = self._current_repo_path()
        self._vm.save_command(repo_path, name, cmd_text)
        self._on_repo_changed(Path(repo_path).name)
