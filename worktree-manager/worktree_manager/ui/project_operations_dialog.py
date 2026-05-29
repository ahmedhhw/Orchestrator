from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QRadioButton, QScrollArea, QVBoxLayout, QWidget,
)

from worktree_manager.models import WorkspaceEntry


class ProjectOperationsDialog(QDialog):
    def __init__(self, parent, vm, repos: dict, on_create=None, on_edit=None,
                 existing_project=None, config_store=None):
        super().__init__(parent)
        self._vm = vm
        self._repos = repos
        self._on_create = on_create
        self._on_edit = on_edit
        self._existing_project = existing_project
        self._editing = existing_project is not None
        self._config_store = config_store
        self._entries: list[str] = []
        self._worktree_path_map: dict[str, str] = {}
        # maps path -> WorktreeStatus for dirty detection
        self._worktree_status_map: dict[str, object] = {}
        # currently-open "New branch here…" panel widget, or None
        self._active_new_branch_panel = None

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
        self._add_repo_btn = QPushButton("+ Add repo…")
        self._add_repo_btn.clicked.connect(self._toggle_add_repo_panel)
        picker.addWidget(self._add_repo_btn)
        self._remove_repo_btn = QPushButton("✕ Remove")
        self._remove_repo_btn.setStyleSheet("background-color: #c0392b; color: white;")
        self._remove_repo_btn.clicked.connect(self._prompt_remove_repo)
        self._remove_repo_btn.setEnabled(bool(self._repo_label_map))
        picker.addWidget(self._remove_repo_btn)
        outer.addLayout(picker)

        # ── Inline remove-repo confirmation row ───────────────────────────────
        self._remove_repo_confirm_row = QWidget()
        confirm_layout = QHBoxLayout(self._remove_repo_confirm_row)
        confirm_layout.setContentsMargins(0, 0, 0, 0)
        self._remove_repo_warn_lbl = QLabel("")
        self._remove_repo_warn_lbl.setStyleSheet("color: #e67e22;")
        confirm_layout.addWidget(self._remove_repo_warn_lbl, 1)
        cancel_rm_btn = QPushButton("Cancel")
        cancel_rm_btn.clicked.connect(self._cancel_remove_repo)
        confirm_layout.addWidget(cancel_rm_btn)
        confirm_rm_btn = QPushButton("Confirm Remove")
        confirm_rm_btn.setStyleSheet("background-color: #c0392b; color: white;")
        confirm_rm_btn.clicked.connect(self._confirm_remove_repo)
        confirm_layout.addWidget(confirm_rm_btn)
        self._remove_repo_confirm_row.setVisible(False)
        outer.addWidget(self._remove_repo_confirm_row)

        # ── Inline add-repo panel (opens below repo picker row) ───────────────
        self._add_repo_panel = self._build_add_repo_panel()
        self._add_repo_panel.setVisible(False)
        outer.addWidget(self._add_repo_panel)

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

    def _build_add_repo_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.NoFrame)
        frame.setStyleSheet(
            "QFrame#addRepoPanel { border-left: 3px solid #27ae60; border-top: none;"
            " border-right: none; border-bottom: none; background: transparent; }"
        )
        frame.setObjectName("addRepoPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 6, 0, 6)
        layout.setSpacing(6)

        repo_row = QHBoxLayout()
        repo_row.addWidget(QLabel("Repo path:"))
        self._add_repo_path_le = QLineEdit()
        self._add_repo_path_le.setPlaceholderText("/path/to/repo")
        self._add_repo_path_le.textChanged.connect(self._on_add_repo_path_changed)
        repo_row.addWidget(self._add_repo_path_le, 1)
        browse_repo_btn = QPushButton("Browse")
        browse_repo_btn.setFixedWidth(70)
        browse_repo_btn.clicked.connect(self._browse_add_repo_path)
        repo_row.addWidget(browse_repo_btn)
        layout.addLayout(repo_row)

        storage_row = QHBoxLayout()
        storage_row.addWidget(QLabel("Worktree storage:"))
        self._add_repo_storage_le = QLineEdit()
        self._add_repo_storage_le.setPlaceholderText("/path/to/repo-worktrees")
        storage_row.addWidget(self._add_repo_storage_le, 1)
        browse_storage_btn = QPushButton("Browse")
        browse_storage_btn.setFixedWidth(70)
        browse_storage_btn.clicked.connect(self._browse_add_repo_storage)
        storage_row.addWidget(browse_storage_btn)
        layout.addLayout(storage_row)

        self._add_repo_error = QLabel("")
        self._add_repo_error.setStyleSheet("color: #e74c3c;")
        self._add_repo_error.setWordWrap(True)
        layout.addWidget(self._add_repo_error)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self._cancel_add_repo)
        btn_row.addWidget(cancel)
        btn_row.addStretch(1)
        confirm = QPushButton("Add Repo")
        confirm.clicked.connect(self._submit_add_repo)
        btn_row.addWidget(confirm)
        layout.addLayout(btn_row)

        return frame

    def _on_add_repo_path_changed(self, text: str) -> None:
        p = Path(text.strip())
        if p.name and not self._add_repo_storage_le.text():
            self._add_repo_storage_le.setText(str(p.parent / (p.name + "-worktrees")))

    def _browse_add_repo_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select repo folder")
        if path:
            self._add_repo_path_le.setText(path)

    def _browse_add_repo_storage(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select worktree storage folder")
        if path:
            self._add_repo_storage_le.setText(path)

    def _toggle_add_repo_panel(self) -> None:
        self._add_repo_panel.setVisible(True)
        self._add_repo_btn.setEnabled(False)
        self._add_repo_error.setText("")
        self._add_repo_path_le.setText("")
        self._add_repo_storage_le.setText("")

    def _cancel_add_repo(self) -> None:
        self._add_repo_panel.setVisible(False)
        self._add_repo_btn.setEnabled(True)
        self._add_repo_error.setText("")

    def _prompt_remove_repo(self) -> None:
        label = self._repo_combo.currentText()
        self._remove_repo_warn_lbl.setText(f'Remove "{label}" from config?')
        self._remove_repo_confirm_row.setVisible(True)
        self._remove_repo_btn.setEnabled(False)
        self._add_repo_btn.setEnabled(False)

    def _cancel_remove_repo(self) -> None:
        self._remove_repo_confirm_row.setVisible(False)
        self._remove_repo_btn.setEnabled(bool(self._repo_label_map))
        self._add_repo_btn.setEnabled(True)

    def _confirm_remove_repo(self) -> None:
        label = self._repo_combo.currentText()
        repo_path = self._repo_label_map.get(label, "")
        if repo_path:
            self._config_store.delete_repo(repo_path)
        self._remove_repo_confirm_row.setVisible(False)

        new_repos = self._config_store.all_repos()
        self._repo_label_map = {Path(p).name: p for p in new_repos.keys()}
        self._repo_combo.blockSignals(True)
        self._repo_combo.clear()
        if self._repo_label_map:
            self._repo_combo.addItems(list(self._repo_label_map.keys()))
        else:
            self._repo_combo.addItem("(no repos)")
        self._repo_combo.blockSignals(False)

        has_repos = bool(self._repo_label_map)
        self._remove_repo_btn.setEnabled(has_repos)
        self._add_repo_btn.setEnabled(True)

        current_label = self._repo_combo.currentText()
        current_path = self._repo_label_map.get(current_label, "")
        if current_path:
            self._refresh_worktrees(current_path)
        else:
            self._render_worktree_rows([])

    def _submit_add_repo(self) -> None:
        self._add_repo_error.setText("")
        repo_path = self._add_repo_path_le.text().strip()
        storage_path = self._add_repo_storage_le.text().strip()

        if not repo_path:
            self._add_repo_error.setText("Error: Repo path is required.")
            return

        if not Path(repo_path).exists():
            self._add_repo_error.setText("Error: Repo path does not exist.")
            return

        if not (Path(repo_path) / ".git").exists():
            self._add_repo_error.setText("Error: Not a valid git repository (no .git found).")
            return

        existing_repos = self._config_store.all_repos()
        if repo_path in existing_repos:
            self._add_repo_error.setText("Error: Repo is already added.")
            return

        if not storage_path:
            storage_path = str(Path(repo_path).parent / (Path(repo_path).name + "-worktrees"))

        from worktree_manager.models import RepoConfig
        from datetime import datetime, timezone
        cfg = RepoConfig(
            repo_path=repo_path,
            worktree_storage=storage_path,
            stale_days=30,
            last_editor="cursor",
            last_editor_mode="reuse",
            last_opened=datetime.now(timezone.utc).isoformat(),
        )
        self._config_store.save_repo(cfg)

        # Rebuild repo label map from store and refresh combo
        new_repos = self._config_store.all_repos()
        self._repo_label_map = {Path(p).name: p for p in new_repos.keys()}
        self._repo_combo.blockSignals(True)
        self._repo_combo.clear()
        self._repo_combo.addItems(list(self._repo_label_map.keys()))
        new_label = Path(repo_path).name
        if new_label in self._repo_label_map:
            self._repo_combo.setCurrentText(new_label)
        self._repo_combo.blockSignals(False)

        self._add_repo_panel.setVisible(False)
        self._add_repo_btn.setEnabled(True)
        self._remove_repo_btn.setEnabled(bool(self._repo_label_map))

        current_label = self._repo_combo.currentText()
        current_path = self._repo_label_map.get(current_label, "")
        if current_path:
            self._refresh_worktrees(current_path)

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
        try:
            statuses = self._vm.list_worktrees_with_dirty(repo_path)
        except Exception:
            statuses = []

        self._worktree_status_map = {s.path: s for s in statuses}

        # Refresh the branch combos in the create-worktree panel
        try:
            all_branches = self._vm.list_branches_for_worktree(repo_path) if statuses else []
        except Exception:
            all_branches = ["main"]

        self._all_branches_cache = all_branches or ["main"]

        self._new_base_combo.clear()
        self._new_base_combo.addItems(self._all_branches_cache)
        self._existing_branch_combo.clear()
        self._existing_branch_combo.addItems(self._all_branches_cache or ["(none)"])

        self._render_worktree_rows(statuses, self._all_branches_cache)

    def _refresh_worktrees_from_cache(self) -> None:
        statuses = list(self._worktree_status_map.values())
        branches = getattr(self, "_all_branches_cache", ["main"])
        self._render_worktree_rows(statuses, branches)

    def _render_worktree_rows(self, statuses: list, branches: list = None) -> None:
        # Clear existing worktree rows
        while self._wt_list_layout.count():
            item = self._wt_list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        self._worktree_path_map = {}
        self._active_new_branch_panel = None
        if branches is None:
            branches = getattr(self, "_all_branches_cache", ["main"])

        for status in statuses:
            wt_name = "(main)" if status.is_main else (Path(status.path).name or status.path)
            self._worktree_path_map[wt_name] = status.path

            row = QHBoxLayout()
            name_lbl = QLabel(f"{wt_name}:")
            row.addWidget(name_lbl)

            branch_combo = QComboBox()
            branch_combo.addItems(branches)
            if status.branch in branches:
                branch_combo.setCurrentText(status.branch)
            _prev = [status.branch]

            def _on_branch_changed(new_branch, path=status.path, combo=branch_combo, prev=_prev):
                if new_branch == prev[0]:
                    return
                try:
                    self._vm.switch_branch_in_project(path, new_branch)
                    prev[0] = new_branch
                except ValueError as e:
                    from PySide6.QtWidgets import QMessageBox
                    combo.blockSignals(True)
                    combo.setCurrentText(prev[0])
                    combo.blockSignals(False)
                    QMessageBox.critical(self, "Cannot switch branch", str(e))

            branch_combo.currentTextChanged.connect(_on_branch_changed)
            row.addWidget(branch_combo, 1)

            if status.has_uncommitted:
                dirty_lbl = QLabel("⚠ dirty")
                dirty_lbl.setStyleSheet("color: #e67e22;")
                row.addWidget(dirty_lbl)

            add_btn = QPushButton("Add")
            add_btn.setFixedWidth(44)
            add_btn.clicked.connect(lambda _=False, p=status.path: self.trigger_add_entry(p))
            row.addWidget(add_btn)

            new_branch_btn = QPushButton("New branch here…")
            new_branch_btn.clicked.connect(
                lambda _=False, p=status.path, s=status: self._toggle_new_branch_panel(p, s)
            )
            row.addWidget(new_branch_btn)

            wrap = QWidget()
            wrap.setLayout(row)
            self._wt_list_layout.addWidget(wrap)

            # placeholder slot for this row's inline "New branch here" panel
            slot = QWidget()
            slot.setVisible(False)
            slot.setObjectName(f"nb_slot_{status.path}")
            self._wt_list_layout.addWidget(slot)

        if not statuses:
            self._wt_list_layout.addWidget(QLabel("(no worktrees)"))

    def _new_branch_here_panel_visible(self) -> bool:
        return (
            self._active_new_branch_panel is not None
            and self._active_new_branch_panel.isVisibleTo(self)
        )

    def _toggle_new_branch_panel(self, worktree_path: str, status) -> None:
        # Close any currently-open panel
        if self._active_new_branch_panel is not None:
            self._active_new_branch_panel.setVisible(False)
            self._active_new_branch_panel = None

        slot_name = f"nb_slot_{worktree_path}"
        slot = self.findChild(QWidget, slot_name)
        if slot is None:
            return

        # Build panel inside the slot
        panel = self._build_new_branch_panel(worktree_path, status, slot)
        self._active_new_branch_panel = panel
        panel.setVisible(True)

    def _build_new_branch_panel(self, worktree_path: str, status, parent: QWidget) -> QWidget:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(12, 6, 0, 6)
        layout.setSpacing(4)

        dirty = status.has_uncommitted

        if dirty:
            warn = QLabel(
                "⚠ This worktree has uncommitted changes. To avoid merge conflicts "
                "you must branch from the current HEAD. Your uncommitted changes will "
                "carry onto the new branch."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #e67e22;")
            layout.addWidget(warn)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("New branch name:"))
        branch_le = QLineEdit()
        name_row.addWidget(branch_le, 1)
        layout.addLayout(name_row)

        base_row = QHBoxLayout()
        base_row.addWidget(QLabel("Base from:"))
        base_combo = QComboBox()
        if dirty:
            base_combo.addItem("current HEAD")
            base_combo.setEnabled(False)
        else:
            try:
                branches = self._vm.list_branches_for_worktree(worktree_path)
            except Exception:
                branches = []
            base_combo.addItem("current HEAD")
            base_combo.addItems(branches)
            base_combo.setEnabled(True)
        base_row.addWidget(base_combo, 1)
        layout.addLayout(base_row)

        error_lbl = QLabel("")
        error_lbl.setStyleSheet("color: #e74c3c;")
        error_lbl.setWordWrap(True)
        layout.addWidget(error_lbl)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        create_btn = QPushButton("Create branch and checkout")
        for btn in (cancel_btn, create_btn):
            btn.setFlat(False)
            btn.setAutoFillBackground(False)

        def _cancel():
            parent.setVisible(False)
            self._active_new_branch_panel = None

        def _create():
            error_lbl.setText("")
            new_branch = branch_le.text().strip()
            if not new_branch:
                error_lbl.setText("Error: Branch name is required.")
                return
            base_text = base_combo.currentText()
            base = "HEAD" if base_text == "current HEAD" else base_text
            try:
                result = self._vm.checkout_new_branch_on_worktree(worktree_path, new_branch, base)
            except Exception as e:
                stderr = getattr(e, "stderr", None) or str(e)
                error_lbl.setText(f"Error: {stderr.strip()}")
                return
            # Update status map and do a full refresh — but first mutate the
            # cached statuses list so _refresh_worktrees sees the new branch name.
            old = self._worktree_status_map.get(worktree_path)
            from worktree_manager.workspace_projects_vm import WorktreeStatus
            updated = WorktreeStatus(
                path=result.path,
                branch=result.branch,
                is_main=old.is_main if old else False,
                has_uncommitted=result.has_uncommitted,
            )
            self._worktree_status_map[worktree_path] = updated
            self._active_new_branch_panel = None
            # Refresh using the updated in-memory map so we don't need a round-trip
            self._refresh_worktrees_from_cache()

        cancel_btn.clicked.connect(_cancel)
        create_btn.clicked.connect(_create)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

        return parent

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
