from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from worktree_manager.command_runner import RunStatus
from worktree_manager.models import SavedCommand, WorktreeModel


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
        self.resize(440, 460)
        self._vm = vm
        self._locked_repo_path = locked_repo_path
        self._locked_worktree_path = locked_worktree_path
        self._commands: list[SavedCommand] = []
        self._worktrees: list[WorktreeModel] = []
        self._selected_cmd: SavedCommand | None = None
        self._cmd_row_widgets: list[QPushButton] = []
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
        cmd_row.addWidget(QLabel("Command:"))
        cmd_row.addStretch(1)
        self._cmd_filter = QLineEdit()
        self._cmd_filter.setPlaceholderText("Filter…")
        self._cmd_filter.setFixedWidth(160)
        self._cmd_filter.textChanged.connect(self._render_cmd_list)
        cmd_row.addWidget(self._cmd_filter)
        outer.addLayout(cmd_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(160)
        self._cmd_container = QWidget()
        self._cmd_layout = QVBoxLayout(self._cmd_container)
        self._cmd_layout.setContentsMargins(0, 0, 0, 0)
        self._cmd_layout.setSpacing(1)
        self._cmd_layout.addStretch(1)
        self._scroll.setWidget(self._cmd_container)
        outer.addWidget(self._scroll, 1)

        self._conflict_label = QLabel("")
        self._conflict_label.setStyleSheet("color: red;")
        self._conflict_label.setWordWrap(True)
        outer.addWidget(self._conflict_label)
        self._restart_btn = _TrackableButton("Restart")
        self._restart_btn.setFixedWidth(80)
        self._restart_btn.clicked.connect(self._trigger_conflict_restart)
        self._restart_btn.set_shown(False)
        outer.addWidget(self._restart_btn)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        launch = QPushButton("Launch")
        launch.clicked.connect(self.trigger_launch)
        btns.addWidget(launch)
        outer.addLayout(btns)

        if self._locked_repo_path:
            self._on_repo_changed(Path(self._locked_repo_path).name)
        elif default_name:
            self._on_repo_changed(default_name)

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
            display = f"{cmd.name}   —   {cmd.command}".replace("&", "&&")
            row = QPushButton(display)
            row.setStyleSheet("text-align: left; padding: 6px;")
            row.clicked.connect(lambda _c=False, c=cmd: self._select_cmd(c))
            self._cmd_layout.addWidget(row)
            self._cmd_row_widgets.append(row)

        self._cmd_layout.addStretch(1)
        self._select_cmd(visible[0])

    def _select_cmd(self, cmd: SavedCommand) -> None:
        self._selected_cmd = cmd
        visible = self._visible_cmds()
        for row, vcmd in zip(self._cmd_row_widgets, visible):
            if vcmd is cmd:
                row.setStyleSheet(
                    "text-align: left; padding: 6px;"
                    " background-color: #4a90d9; color: white;"
                )
            else:
                row.setStyleSheet("text-align: left; padding: 6px;")

    def _current_repo_path(self) -> str:
        if self._locked_repo_path:
            return self._locked_repo_path
        return self._repo_map.get(self._repo_combo.currentText(), "")

    def _current_worktree_path(self) -> str:
        if self._locked_worktree_path:
            return self._locked_worktree_path
        label = self._wt_combo.currentText()
        for wt in self._worktrees:
            if wt.path in label:
                return wt.path
        return label

    # --- public API for tests ---

    def command_choices(self) -> list[str]:
        return [c.name for c in self._commands]

    def worktree_choices(self) -> list[str]:
        return [f"{wt.branch}  ({wt.path})" for wt in self._worktrees]

    def set_command(self, name: str) -> None:
        for cmd in self._commands:
            if cmd.name == name:
                self._select_cmd(cmd)
                return

    def set_worktree(self, path: str) -> None:
        for i, wt in enumerate(self._worktrees):
            if wt.path == path:
                self._wt_combo.setCurrentIndex(i)
                return

    def trigger_launch(self) -> None:
        if self._selected_cmd is None:
            return
        cmd_obj = self._selected_cmd
        repo_path = self._current_repo_path()
        worktree_path = self._current_worktree_path()
        repo_name = Path(repo_path).name

        existing = None
        if hasattr(self._vm, "find_existing_run"):
            existing = self._vm.find_existing_run(
                cmd_obj.name, repo_path, worktree_path,
            )

        if existing is not None:
            if existing.status == RunStatus.RUNNING:
                self._show_conflict(
                    f'"{cmd_obj.name}" is already running in this worktree.',
                    show_restart=False, run_id=None,
                )
            else:
                self._show_conflict(
                    f'"{cmd_obj.name}" already exists but is stopped. Restart it?',
                    show_restart=True, run_id=existing.run_id,
                )
            return

        self._vm.launch(
            repo_path=repo_path, repo_name=repo_name,
            cmd_name=cmd_obj.name, command_str=cmd_obj.command,
            worktree_path=worktree_path,
            startup_pattern=getattr(cmd_obj, "startup_pattern", None),
        )
        if hasattr(self._vm, "set_last_used_repo"):
            self._vm.set_last_used_repo(repo_path)
        self.accept()

    def _show_conflict(self, message: str, show_restart: bool,
                       run_id: str | None) -> None:
        self._conflict_label.setText(message)
        self._conflict_run_id = run_id
        self._restart_btn.set_shown(show_restart)

    def _trigger_conflict_restart(self) -> None:
        if self._conflict_run_id and hasattr(self._vm, "restart"):
            self._vm.restart(self._conflict_run_id)
        self.accept()
