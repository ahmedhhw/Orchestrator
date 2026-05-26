from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from worktree_manager.models import WorkspaceEntry


class ProjectOperationsDialog(QDialog):
    def __init__(self, parent, vm, repos: dict, on_create=None, on_edit=None,
                 existing_project=None):
        super().__init__(parent)
        self._vm = vm
        self._repos = repos
        self._on_create = on_create
        self._on_edit = on_edit
        self._existing_project = existing_project
        self._editing = existing_project is not None
        self._entries: list[str] = []
        self._worktree_path_map: dict[str, str] = {}

        self.setWindowTitle("Edit Project" if self._editing else "New Workspace Project")
        self.setModal(True)
        self._build()
        if self._editing:
            self._prepopulate(existing_project)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(4)

        title = QLabel("Edit Project" if self._editing else "New Workspace Project")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        outer.addWidget(title)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Project name:"))
        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(lambda _t: self._name_warn.setText(""))
        name_row.addWidget(self._name_edit, 1)
        outer.addLayout(name_row)

        self._name_warn = QLabel("")
        self._name_warn.setStyleSheet("color: #e74c3c;")
        outer.addWidget(self._name_warn)

        outer.addWidget(QLabel("Add worktrees:"))
        picker = QHBoxLayout()
        picker.addWidget(QLabel("Repo:"))
        self._repo_combo = QComboBox()
        repo_names = list(self._repos.keys())
        self._repo_label_map = {Path(p).name: p for p in repo_names}
        self._repo_combo.addItems(list(self._repo_label_map.keys()) or ["(no repos)"])
        self._repo_combo.currentTextChanged.connect(self._on_repo_changed)
        picker.addWidget(self._repo_combo, 1)
        picker.addWidget(QLabel("Worktree:"))
        self._wt_combo = QComboBox()
        picker.addWidget(self._wt_combo, 1)
        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(self._add_selected)
        picker.addWidget(add_btn)
        outer.addLayout(picker)

        if repo_names:
            self._refresh_worktrees(repo_names[0])

        outer.addWidget(QLabel("Entries:"))
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_scroll.setWidget(self._list_container)
        outer.addWidget(self._list_scroll, 1)

        self._entries_warn = QLabel("")
        self._entries_warn.setStyleSheet("color: #e74c3c;")
        outer.addWidget(self._entries_warn)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        btn_row.addStretch(1)
        confirm = QPushButton("Save Changes" if self._editing else "Create Project")
        confirm.clicked.connect(self.trigger_confirm)
        btn_row.addWidget(confirm)
        outer.addLayout(btn_row)
        self._refresh_entry_list()

    def _on_repo_changed(self, display_name: str) -> None:
        path = self._repo_label_map.get(display_name, "")
        if path:
            self._refresh_worktrees(path)

    def _refresh_worktrees(self, repo_path: str) -> None:
        try:
            worktrees = self._vm.list_worktrees_for_repo(repo_path)
        except Exception:
            worktrees = []
        paths = [wt.path for wt in worktrees]
        display = [
            f"(main): {wt.branch}" if wt.is_main else f"{Path(wt.path).name or wt.path}: {wt.branch}"
            for wt in worktrees
        ]
        self._worktree_path_map = dict(zip(display, paths))
        self._wt_combo.clear()
        self._wt_combo.addItems(display or ["(none)"])

    def _add_selected(self) -> None:
        display = self._wt_combo.currentText()
        if not display or display in ("(none)", "(select repo first)"):
            return
        path = self._worktree_path_map.get(display, display)
        if path:
            self.trigger_add_entry(path)

    def trigger_add_entry(self, path: str) -> None:
        if path in self._entries:
            return
        self._entries.append(path)
        self._entries_warn.setText("")
        self._refresh_entry_list()

    def trigger_remove_entry(self, path: str) -> None:
        if path in self._entries:
            self._entries.remove(path)
        self._refresh_entry_list()

    def _refresh_entry_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        if not self._entries:
            empty = QLabel("(none)")
            empty.setStyleSheet("color: gray;")
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch(1)
            return
        for path in list(self._entries):
            row = QHBoxLayout()
            lbl = QLabel(path)
            row.addWidget(lbl, 1)
            rm = QPushButton("✕")
            rm.setFixedWidth(28)
            rm.setStyleSheet("background-color: #c0392b; color: white;")
            rm.clicked.connect(lambda _=False, p=path: self.trigger_remove_entry(p))
            row.addWidget(rm)
            wrap = QWidget()
            wrap.setLayout(row)
            self._list_layout.addWidget(wrap)
        self._list_layout.addStretch(1)

    def _prepopulate(self, project) -> None:
        self._name_edit.setText(project.name)
        for entry in project.entries:
            self.trigger_add_entry(entry.worktree_path)

    def trigger_confirm(self) -> None:
        name = self._name_edit.text().strip()
        valid = True
        if not name:
            self._name_warn.setText("Project name is required.")
            valid = False
        if not self._entries:
            self._entries_warn.setText("Add at least one worktree.")
            valid = False
        if not valid:
            return
        entries = [WorkspaceEntry(worktree_path=p) for p in self._entries]
        try:
            if self._editing:
                self._on_edit(self._existing_project.name, name, entries)
            else:
                self._on_create(name, entries)
        except Exception as e:
            self._name_warn.setText(f"Error: {e}")
            return
        self.accept()

    # --- public test API ---

    def get_name(self) -> str:
        return self._name_edit.text()

    def get_entries(self) -> list[str]:
        return list(self._entries)
