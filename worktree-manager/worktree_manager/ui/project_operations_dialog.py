from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QRadioButton, QScrollArea, QVBoxLayout, QWidget,
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
        # maps path -> WorktreeStatus for dirty detection
        self._worktree_status_map: dict[str, object] = {}

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
        outer.addLayout(picker)

        # ── "Worktrees in <repo>:"  [+ Create new worktree ▾] header row ─────
        wt_header_row = QHBoxLayout()
        self._wt_section_label = QLabel("Worktrees:")
        wt_header_row.addWidget(self._wt_section_label, 1)
        self._create_wt_toggle_btn = QPushButton("+ Create new worktree ▾")
        self._create_wt_toggle_btn.clicked.connect(self._toggle_create_wt_panel)
        wt_header_row.addWidget(self._create_wt_toggle_btn)
        outer.addLayout(wt_header_row)

        # ── Inline create-worktree panel (opens below header, above list) ─────
        self._create_wt_panel = self._build_create_wt_panel()
        self._create_wt_panel.setVisible(False)
        outer.addWidget(self._create_wt_panel)

        # ── Worktree list with dirty markers ──────────────────────────────────
        self._wt_list_widget = QWidget()
        self._wt_list_layout = QVBoxLayout(self._wt_list_widget)
        self._wt_list_layout.setContentsMargins(0, 0, 0, 0)
        self._wt_list_layout.setSpacing(2)
        outer.addWidget(self._wt_list_widget)

        # ─────────────────────────────────────────────────────────────────────
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

        self._entries_dirty_warn = QLabel("")
        self._entries_dirty_warn.setStyleSheet("color: #e67e22;")
        outer.addWidget(self._entries_dirty_warn)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        btn_row.addStretch(1)
        confirm = QPushButton("Save Changes" if self._editing else "Create Project")
        confirm.clicked.connect(self.trigger_confirm)
        btn_row.addWidget(confirm)
        outer.addLayout(btn_row)

        if repo_names:
            self._refresh_worktrees(repo_names[0])

        self._refresh_entry_list()

    def _build_create_wt_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.NoFrame)
        frame.setStyleSheet(
            "QFrame#createWtPanel { border-left: 3px solid #5b8ac7; border-top: none;"
            " border-right: none; border-bottom: none; background: transparent; }"
        )
        frame.setObjectName("createWtPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 6, 0, 6)
        layout.setSpacing(6)

        # Mode radios
        mode_row = QHBoxLayout()
        self._new_branch_radio = QRadioButton("New branch")
        self._new_branch_radio.setChecked(True)
        self._existing_branch_radio = QRadioButton("Existing branch")
        grp = QButtonGroup(frame)
        grp.addButton(self._new_branch_radio)
        grp.addButton(self._existing_branch_radio)
        self._new_branch_radio.toggled.connect(self._update_create_wt_mode)
        mode_row.addWidget(self._new_branch_radio)
        mode_row.addWidget(self._existing_branch_radio)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        # New branch fields
        self._new_branch_frame = QWidget()
        nb_layout = QVBoxLayout(self._new_branch_frame)
        nb_layout.setContentsMargins(0, 0, 0, 0)
        nb_layout.setSpacing(2)

        nb_layout.addWidget(QLabel("Worktree name:"))
        self._new_wt_name_le = QLineEdit()
        self._new_wt_name_le.setPlaceholderText("fix-auth")
        nb_layout.addWidget(self._new_wt_name_le)

        nb_layout.addWidget(QLabel("Branch name:"))
        self._new_branch_le = QLineEdit()
        self._new_branch_le.setPlaceholderText("fix/auth")
        nb_layout.addWidget(self._new_branch_le)

        nb_layout.addWidget(QLabel("Base branch:"))
        self._new_base_combo = QComboBox()
        self._new_base_combo.addItem("main")
        nb_layout.addWidget(self._new_base_combo)

        layout.addWidget(self._new_branch_frame)

        # Existing branch fields
        self._existing_branch_frame = QWidget()
        ex_layout = QVBoxLayout(self._existing_branch_frame)
        ex_layout.setContentsMargins(0, 0, 0, 0)
        ex_layout.setSpacing(2)

        ex_layout.addWidget(QLabel("Existing branch:"))
        self._existing_branch_combo = QComboBox()
        ex_layout.addWidget(self._existing_branch_combo)

        ex_layout.addWidget(QLabel("Worktree name:"))
        self._existing_wt_name_le = QLineEdit()
        self._existing_wt_name_le.setPlaceholderText("fix-auth")
        ex_layout.addWidget(self._existing_wt_name_le)

        layout.addWidget(self._existing_branch_frame)
        self._existing_branch_frame.setVisible(False)

        # Inline error label
        self._create_wt_error = QLabel("")
        self._create_wt_error.setStyleSheet("color: #e74c3c;")
        self._create_wt_error.setWordWrap(True)
        layout.addWidget(self._create_wt_error)

        # Buttons
        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self._cancel_create_wt)
        btn_row.addWidget(cancel)
        btn_row.addStretch(1)
        create = QPushButton("Create + Add")
        create.clicked.connect(self._submit_create_wt)
        btn_row.addWidget(create)
        layout.addLayout(btn_row)

        return frame

    def _update_create_wt_mode(self):
        is_new = self._new_branch_radio.isChecked()
        self._new_branch_frame.setVisible(is_new)
        self._existing_branch_frame.setVisible(not is_new)

    def _toggle_create_wt_panel(self):
        visible = not self._create_wt_panel.isVisible()
        self._create_wt_panel.setVisible(visible)
        self._create_wt_error.setText("")
        if visible:
            self._new_branch_radio.setChecked(True)
            self._update_create_wt_mode()

    def _cancel_create_wt(self):
        self._create_wt_panel.setVisible(False)
        self._create_wt_error.setText("")

    def _submit_create_wt(self):
        self._create_wt_error.setText("")
        repo_label = self._repo_combo.currentText()
        repo_path = self._repo_label_map.get(repo_label, "")

        if self._new_branch_radio.isChecked():
            wt_name = self._new_wt_name_le.text().strip()
            branch = self._new_branch_le.text().strip()
            base = self._new_base_combo.currentText()
            if not wt_name or not branch:
                self._create_wt_error.setText("Error: Worktree name and branch name are required.")
                return
            wt_path = str(Path(repo_path).parent / wt_name) if repo_path else f"/{wt_name}"
            spec = {"mode": "new", "worktree_path": wt_path, "branch": branch, "base_branch": base}
        else:
            branch = self._existing_branch_combo.currentText()
            wt_name = self._existing_wt_name_le.text().strip() or branch.replace("/", "-")
            if not branch or branch == "(none)":
                self._create_wt_error.setText("Error: Select a branch.")
                return
            wt_path = str(Path(repo_path).parent / wt_name) if repo_path else f"/{wt_name}"
            spec = {"mode": "existing", "worktree_path": wt_path, "branch": branch}

        try:
            status = self._vm.create_worktree_for_project(repo_path, spec)
        except Exception as e:
            stderr = getattr(e, "stderr", None) or str(e)
            self._create_wt_error.setText(f"Error: {stderr.strip()}")
            return

        self.trigger_add_entry(status.path)
        self._create_wt_panel.setVisible(False)
        self._refresh_worktrees(repo_path)

    def _on_repo_changed(self, display_name: str) -> None:
        path = self._repo_label_map.get(display_name, "")
        if path:
            self._refresh_worktrees(path)

    def _refresh_worktrees(self, repo_path: str) -> None:
        # Clear existing worktree rows
        while self._wt_list_layout.count():
            item = self._wt_list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        try:
            statuses = self._vm.list_worktrees_with_dirty(repo_path)
        except Exception:
            statuses = []

        self._worktree_status_map = {s.path: s for s in statuses}
        self._worktree_path_map = {}

        # Also refresh the base branch combo and existing branch combo
        try:
            all_branches = self._vm.list_branches_for_worktree(repo_path) if statuses else []
        except Exception:
            all_branches = ["main"]

        self._new_base_combo.clear()
        self._new_base_combo.addItems(all_branches or ["main"])
        self._existing_branch_combo.clear()
        self._existing_branch_combo.addItems(all_branches or ["(none)"])

        for status in statuses:
            if status.is_main:
                display = f"(main): {status.branch}"
            else:
                display = f"{Path(status.path).name or status.path}: {status.branch}"
            self._worktree_path_map[display] = status.path

            row = QHBoxLayout()
            name_lbl = QLabel(display)
            row.addWidget(name_lbl, 1)

            if status.has_uncommitted:
                dirty_lbl = QLabel("⚠ dirty")
                dirty_lbl.setStyleSheet("color: #e67e22;")
                row.addWidget(dirty_lbl)

            add_btn = QPushButton("Add")
            add_btn.setFixedWidth(44)
            add_btn.clicked.connect(lambda _=False, p=status.path: self.trigger_add_entry(p))
            row.addWidget(add_btn)

            new_branch_btn = QPushButton("New branch here…")
            row.addWidget(new_branch_btn)

            wrap = QWidget()
            wrap.setLayout(row)
            self._wt_list_layout.addWidget(wrap)

        if not statuses:
            self._wt_list_layout.addWidget(QLabel("(no worktrees)"))

    def _add_selected(self) -> None:
        # Legacy path — kept for compatibility; the new UI uses per-row Add buttons
        pass

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

        dirty_count = 0
        if not self._entries:
            empty = QLabel("(none)")
            empty.setStyleSheet("color: gray;")
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch(1)
            self._entries_dirty_warn.setText("")
            return

        for path in list(self._entries):
            status = self._worktree_status_map.get(path)
            is_dirty = status.has_uncommitted if status else False
            if is_dirty:
                dirty_count += 1

            row = QHBoxLayout()
            if is_dirty:
                dirty_marker = QLabel("⚠")
                dirty_marker.setStyleSheet("color: #e67e22;")
                row.addWidget(dirty_marker)
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

        if dirty_count > 0:
            self._entries_dirty_warn.setText(
                f"⚠ {dirty_count} {'entry has' if dirty_count == 1 else 'entries have'} "
                "uncommitted changes. You can still save the project."
            )
        else:
            self._entries_dirty_warn.setText("")

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
