import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton,
    QRadioButton, QScrollArea, QVBoxLayout, QWidget,
)

from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog


class WorkspaceProjectsPanel(QWidget):
    def __init__(self, parent, vm, on_close,
                 on_generate_project=None, on_run_command=None, on_nickname=None,
                 confirm_fn=None):
        super().__init__(parent)
        self._vm = vm
        self._on_close = on_close
        self._on_generate_project = on_generate_project
        self._on_run_command = on_run_command
        self._on_nickname = on_nickname
        self._confirm_fn = confirm_fn
        self._collapsed: set[str] = set(vm._store.get_ui_pref("projects_collapsed", []))
        self._editor: str = vm._store.get_ui_pref("projects_editor", "cursor")
        self._empty_visible: bool = True
        self._entry_rows: list[QWidget] = []
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        toolbar = QHBoxLayout()
        title = QLabel("Workspace Projects")
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        new_btn = QPushButton("+ New")
        new_btn.clicked.connect(self._open_new_dialog)
        toolbar.addWidget(new_btn)
        close_btn = QPushButton("×")
        close_btn.setFixedWidth(32)
        close_btn.clicked.connect(self.trigger_close)
        toolbar.addWidget(close_btn)
        outer.addLayout(toolbar)

        editor_row = QHBoxLayout()
        editor_row.addWidget(QLabel("Editor:"))
        self._editor_group = QButtonGroup(self)
        for name in ("cursor", "vscode"):
            rb = QRadioButton(name)
            rb.setChecked(name == self._editor)
            rb.toggled.connect(lambda checked, n=name: checked and self._set_editor(n))
            self._editor_group.addButton(rb)
            editor_row.addWidget(rb)
        editor_row.addStretch(1)
        outer.addLayout(editor_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll_container = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_container)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(4)
        self._scroll.setWidget(self._scroll_container)
        outer.addWidget(self._scroll, 1)

    def _set_editor(self, name: str):
        self._editor = name
        self._vm._store.set_ui_pref("projects_editor", name)

    def refresh(self):
        self._entry_rows.clear()
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        projects = self._vm.load_projects()
        if not projects:
            empty = QLabel("No projects yet.\nClick [+ New] to create one.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: gray;")
            self._scroll_layout.addWidget(empty)
            self._scroll_layout.addStretch(1)
            self._empty_visible = True
            return
        self._empty_visible = False
        for project in projects:
            self._add_project_row(project)
        self._scroll_layout.addStretch(1)

    def empty_state_visible(self) -> bool:
        return self._empty_visible

    def _attach_nickname_menu(self, btn: QPushButton, action_name: str, args: dict) -> None:
        if self._on_nickname is None:
            return
        btn.setContextMenuPolicy(Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda pos, a=action_name, kw=args: self._show_nickname_menu(btn, a, kw)
        )

    def _show_nickname_menu(self, btn: QPushButton, action_name: str, args: dict) -> None:
        menu = QMenu(self)
        act = menu.addAction("Add Nickname…")
        act.triggered.connect(lambda: self._on_nickname(action_name, args))
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _add_project_row(self, project):
        name = project.name
        is_collapsed = name in self._collapsed

        header = QHBoxLayout()
        toggle = QPushButton(f"{'▶' if is_collapsed else '▼'} {name}")
        toggle.setStyleSheet("text-align: left; padding: 4px;")
        toggle.clicked.connect(lambda _=False, n=name: self.toggle_collapse(n))
        header.addWidget(toggle, 1)
        open_btn = QPushButton("Open")
        open_btn.setFixedWidth(56)
        open_btn.clicked.connect(lambda _=False, n=name: self.open_project(n))
        self._attach_nickname_menu(open_btn, "open_project", {"name": name})
        header.addWidget(open_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setFixedWidth(48)
        edit_btn.clicked.connect(lambda _=False, p=project: self._edit_project(p))
        self._attach_nickname_menu(edit_btn, "edit_project", {"name": name})
        header.addWidget(edit_btn)
        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(28)
        del_btn.setStyleSheet("background-color: #c0392b; color: white;")
        del_btn.clicked.connect(lambda _=False, n=name: self.delete_project(n))
        self._attach_nickname_menu(del_btn, "delete_project", {"name": name})
        header.addWidget(del_btn)
        wrap = QWidget()
        wrap.setLayout(header)
        self._scroll_layout.addWidget(wrap)

        if not is_collapsed:
            for entry in project.entries:
                self._add_entry_row(entry.worktree_path)

    def _add_entry_row(self, worktree_path: str):
        try:
            current_branch = self._vm._git.checked_out_branch(worktree_path)
            branches = self._vm.list_branches_for_worktree(worktree_path)
        except Exception:
            current_branch = "(unknown)"
            branches = []
        wt_name = os.path.basename(worktree_path) or worktree_path
        home = os.path.expanduser("~")
        short = "~" + worktree_path[len(home):] if worktree_path.startswith(home) else worktree_path

        row = QHBoxLayout()
        lbl = QLabel(f"    {wt_name}")
        lbl.setStyleSheet("color: gray;")
        lbl.setToolTip(worktree_path)
        row.addWidget(lbl, 1)
        if branches:
            combo = QComboBox()
            combo.addItems(branches)
            if current_branch in branches:
                combo.setCurrentText(current_branch)
            combo.setMinimumWidth(140)
            combo.currentTextChanged.connect(
                lambda new, p=worktree_path, orig=current_branch:
                    self._on_branch_changed(p, orig, new)
            )
            row.addWidget(combo)
        else:
            row.addWidget(QLabel(current_branch))
        wrap = QWidget()
        wrap.setLayout(row)
        wrap.setContextMenuPolicy(Qt.CustomContextMenu)
        wrap.customContextMenuRequested.connect(
            lambda pos, p=worktree_path, w=wrap: self._show_entry_context_menu(p, pos, w)
        )
        self._entry_rows.append(wrap)
        self._scroll_layout.addWidget(wrap)

    def _build_entry_context_menu(self, worktree_path: str) -> QMenu:
        menu = QMenu(self)
        gen_act = menu.addAction("Generate Project")
        gen_act.triggered.connect(lambda: self._trigger_generate_project(worktree_path))
        run_act = menu.addAction("Run Command…")
        run_act.triggered.connect(lambda: self._trigger_run_command(worktree_path))
        return menu

    def _show_entry_context_menu(self, worktree_path: str, pos, row: QWidget):
        self._build_entry_context_menu(worktree_path).exec(row.mapToGlobal(pos))

    def _trigger_generate_project(self, worktree_path: str):
        if self._on_generate_project:
            self._on_generate_project(worktree_path)

    def _trigger_run_command(self, worktree_path: str):
        if self._on_run_command:
            self._on_run_command(worktree_path)

    def _on_branch_changed(self, path: str, orig: str, new: str):
        if new == orig:
            return
        try:
            self.switch_branch(path, new)
        except ValueError as e:
            QMessageBox.critical(self, "Cannot switch", str(e))
        self.refresh()

    # --- public API ---

    def switch_branch(self, worktree_path: str, new_branch: str) -> None:
        self._vm.switch_branch_in_project(worktree_path, new_branch)

    def toggle_collapse(self, name: str) -> None:
        if name in self._collapsed:
            self._collapsed.discard(name)
        else:
            self._collapsed.add(name)
        self._vm._store.set_ui_pref("projects_collapsed", list(self._collapsed))
        self.refresh()

    def open_project(self, name: str) -> None:
        self._vm.open_project(name, self._editor)

    def _confirm(self, message: str) -> bool:
        if self._confirm_fn is not None:
            return self._confirm_fn(message)
        return QMessageBox.question(
            self, "Confirm", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes

    def delete_project(self, name: str) -> None:
        if not self._confirm(f'Delete project "{name}"?'):
            return
        self._vm.delete_project(name)
        self.refresh()

    def trigger_close(self) -> None:
        self._on_close()

    def _open_new_dialog(self) -> None:
        dlg = ProjectOperationsDialog(
            parent=self, vm=self._vm,
            repos=self._vm._store.all_repos(),
            on_create=self._handle_create,
        )
        dlg.exec()

    def _edit_project(self, project) -> None:
        dlg = ProjectOperationsDialog(
            parent=self, vm=self._vm,
            repos=self._vm._store.all_repos(),
            on_edit=self._handle_edit,
            existing_project=project,
        )
        dlg.exec()

    def _handle_create(self, name: str, entries: list) -> None:
        self._vm.create_project(name=name, entries=entries)
        self.refresh()

    def _handle_edit(self, old_name: str, new_name: str, entries: list) -> None:
        self._vm.update_project(old_name=old_name, new_name=new_name, entries=entries)
        self.refresh()
