import os

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from worktree_manager.ui.cleanup_wizard import (
    _group_candidates, _merged_subgroups, _reason,
)


class BranchManagementPanel(QWidget):
    def __init__(self, vm=None, parent=None):
        super().__init__(parent)
        self._vm = vm

        # cleanup UI state
        self._pairs: list = []              # (CleanupCandidate, QCheckBox)
        self._protected_pairs: list = []   # (CleanupCandidate, QCheckBox)
        self._subgroup_btns: dict = {}
        self._stale_btn: QPushButton | None = None
        self._global_btn: QPushButton | None = None
        self._admin_mode = False
        self._admin_banner: QWidget | None = None
        self._current_repo_path: str | None = None  # None = "all repos"
        self._cleanup_content: QWidget | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # section tab strip
        tab_strip = QHBoxLayout()
        tab_strip.setContentsMargins(8, 8, 8, 0)
        tab_strip.setSpacing(4)

        self._sync_btn = QPushButton("Sync from origin")
        self._sync_btn.setCheckable(True)
        self._sync_btn.clicked.connect(lambda: self._switch_section("sync"))
        tab_strip.addWidget(self._sync_btn)

        self._cleanup_btn = QPushButton("Cleanup")
        self._cleanup_btn.setCheckable(True)
        self._cleanup_btn.clicked.connect(lambda: self._switch_section("cleanup"))
        tab_strip.addWidget(self._cleanup_btn)

        tab_strip.addStretch(1)
        outer.addLayout(tab_strip)

        # stacked content area
        self._content_area = QVBoxLayout()
        self._content_area.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._content_area, 1)

        # start on sync (placeholder)
        self._switch_section("sync")

    # ── section switching ──────────────────────────────────────────────────

    def _switch_section(self, section: str) -> None:
        self._sync_btn.setChecked(section == "sync")
        self._cleanup_btn.setChecked(section == "cleanup")
        self._clear_content()
        if section == "sync":
            self._build_sync_placeholder()
        else:
            if self._vm is not None:
                self._build_cleanup_ui(self._current_repo_path)
            else:
                self._build_cleanup_placeholder()

    def _clear_content(self):
        while self._content_area.count():
            item = self._content_area.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._pairs = []
        self._protected_pairs = []
        self._subgroup_btns = {}
        self._stale_btn = None
        self._global_btn = None
        self._admin_banner = None

    def _build_sync_placeholder(self):
        lbl = QLabel("Coming soon — Sync from origin will live here.")
        lbl.setAlignment(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.AlignCenter)
        lbl.setStyleSheet("color: gray; font-size: 14px;")
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_area.addWidget(lbl)

    def _build_cleanup_placeholder(self):
        lbl = QLabel("Coming soon — Cleanup will live here.")
        lbl.setAlignment(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.AlignCenter)
        lbl.setStyleSheet("color: gray; font-size: 14px;")
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_area.addWidget(lbl)

    # ── public API ─────────────────────────────────────────────────────────

    def show_cleanup(self, repo_path: str | None) -> None:
        """Switch to Cleanup section, pre-select repo_path (None = all repos)."""
        self._current_repo_path = repo_path
        self._switch_section("cleanup")

    # ── cleanup UI builder ─────────────────────────────────────────────────

    def _build_cleanup_ui(self, repo_path: str | None):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        # repo selector row
        selector_row = QHBoxLayout()
        selector_label = QLabel("Repo:")
        selector_row.addWidget(selector_label)
        self._repo_combo = QComboBox()
        self._repo_combo.addItem("all repos", None)
        repos = self._vm.list_repos()
        for path in repos:
            self._repo_combo.addItem(os.path.basename(path.rstrip("/")), path)
        if repo_path is not None:
            idx = self._repo_combo.findData(repo_path)
            if idx >= 0:
                self._repo_combo.setCurrentIndex(idx)
        self._repo_combo.currentIndexChanged.connect(self._on_repo_selected)
        selector_row.addWidget(self._repo_combo)
        selector_row.addStretch(1)
        layout.addLayout(selector_row)

        # admin banner (hidden by default)
        self._admin_banner = QLabel(
            "⚠ Admin Mode: Protected branches can be deleted.\n"
            "    Double-check your selection before deleting."
        )
        self._admin_banner.setStyleSheet(
            "background-color: #7b2d00; color: white; padding: 6px 12px;"
        )
        self._admin_banner.setVisible(False)
        layout.addWidget(self._admin_banner)

        # scrollable branch list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        list_container = QWidget()
        self._list_layout = QVBoxLayout(list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        scroll.setWidget(list_container)
        layout.addWidget(scroll, 1)

        # bottom bar
        admin_row = QHBoxLayout()
        admin_cb = QCheckBox("Admin Mode")
        admin_cb.toggled.connect(self._set_admin_mode)
        admin_row.addWidget(admin_cb)
        admin_warn = QLabel("⚠ Enable only if you know what you're doing")
        admin_warn.setStyleSheet("color: orange;")
        admin_row.addWidget(admin_warn)
        admin_row.addStretch(1)
        layout.addLayout(admin_row)

        btn_row = QHBoxLayout()
        self._global_btn = QPushButton("Select All")
        self._global_btn.clicked.connect(self._trigger_select_all)
        btn_row.addWidget(self._global_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._clear_content)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch(1)
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet("background-color: #c0392b; color: white;")
        delete_btn.clicked.connect(self._trigger_delete)
        btn_row.addWidget(delete_btn)
        layout.addLayout(btn_row)

        self._content_area.addWidget(container)

        # load and render candidates
        selected_path = self._repo_combo.currentData()
        self._load_and_render(selected_path)

    def _on_repo_selected(self):
        selected = self._repo_combo.currentData()
        self._load_and_render(selected)

    def _load_and_render(self, repo_path):
        # clear old list
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._pairs = []
        self._protected_pairs = []
        self._subgroup_btns = {}
        self._stale_btn = None

        candidates = self._vm.load_cleanup_candidates(repo_path)
        grouped = _group_candidates(candidates)
        self._render_merged(grouped["merged"])
        self._render_stale(grouped["stale"])
        self._render_healthy(grouped["healthy"])
        self._render_protected(grouped["protected"])
        self._render_unoperable(grouped["unoperable"])
        self._list_layout.addStretch(1)
        self._refresh_button_labels()

    # ── rendering helpers (mirrors CleanupWizard) ──────────────────────────

    _ROW_INDENT = 20

    def _gray_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: gray;")
        return lbl

    def _add_section_label(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: gray;")
        self._list_layout.addWidget(lbl)

    def _add_indented_row(self, *widgets, stretch_last=True):
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(self._ROW_INDENT, 0, 0, 0)
        row.setSpacing(8)
        for w in widgets:
            row.addWidget(w)
        if stretch_last:
            row.addStretch(1)
        self._list_layout.addWidget(wrap)

    def _add_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: gray;")
        self._list_layout.addWidget(line)

    def _add_checkbox(self, c, default_checked: bool):
        cb = QCheckBox(f"{c.branch}  ({_reason(c)})")
        cb.setChecked(default_checked)
        cb.toggled.connect(lambda _=False: self._refresh_button_labels())
        self._add_indented_row(cb)
        self._pairs.append((c, cb))

    def _render_merged(self, merged: list):
        self._add_section_label("Merged:")
        if not merged:
            self._add_indented_row(self._gray_label("(none)"))
            return
        for target, branches in _merged_subgroups(merged):
            tlabel = self._gray_label(f"→ into {target}")
            btn = QPushButton("Select all")
            btn.setFixedWidth(90)
            btn.clicked.connect(lambda _=False, t=target: self._trigger_subgroup_select(t))
            self._subgroup_btns[target] = btn
            wrap = QWidget()
            row = QHBoxLayout(wrap)
            row.setContentsMargins(self._ROW_INDENT, 0, 0, 0)
            row.setSpacing(8)
            row.addWidget(tlabel)
            row.addStretch(1)
            row.addWidget(btn)
            self._list_layout.addWidget(wrap)
            for c in branches:
                self._add_checkbox(c, default_checked=True)

    def _render_stale(self, stale: list):
        self._add_divider()
        header = QHBoxLayout()
        lbl = QLabel("Stale:")
        lbl.setStyleSheet("color: gray;")
        header.addWidget(lbl)
        header.addStretch(1)
        if stale:
            self._stale_btn = QPushButton("Select all")
            self._stale_btn.setFixedWidth(90)
            self._stale_btn.clicked.connect(self._trigger_stale_select)
            header.addWidget(self._stale_btn)
        wrap = QWidget()
        wrap.setLayout(header)
        self._list_layout.addWidget(wrap)
        if not stale:
            self._add_indented_row(self._gray_label("(none)"))
            return
        for c in stale:
            self._add_checkbox(c, default_checked=True)

    def _render_healthy(self, healthy: list):
        self._add_divider()
        self._add_section_label("Healthy:")
        if not healthy:
            self._add_indented_row(self._gray_label("(none)"))
            return
        for c in healthy:
            self._add_checkbox(c, default_checked=False)

    def _render_protected(self, protected: list):
        if not protected:
            return
        self._add_divider()
        self._add_section_label("Protected:")
        for c in protected:
            cb = QCheckBox(f"{c.branch}  ({_reason(c)})")
            cb.setEnabled(False)
            tag = QLabel("⚠ main" if c.branch == "main" else "⚠ feature")
            tag.setStyleSheet("color: orange;")
            self._add_indented_row(cb, tag)
            self._protected_pairs.append((c, cb))

    def _render_unoperable(self, unoperable: list):
        if not unoperable:
            return
        self._add_divider()
        self._add_section_label("Cannot delete:")
        for c in unoperable:
            txt = QLabel(f"—   {c.branch}  ({_reason(c)})")
            txt.setStyleSheet("color: gray;")
            tag = QLabel("⚠ uncommitted" if c.has_uncommitted else "⚠ checked out")
            tag.setStyleSheet("color: orange;")
            self._add_indented_row(txt, tag)

    # ── admin mode ─────────────────────────────────────────────────────────

    def _set_admin_mode(self, on: bool) -> None:
        self._admin_mode = bool(on)
        if self._admin_banner is not None:
            self._admin_banner.setVisible(self._admin_mode)
        for _, cb in self._protected_pairs:
            if self._admin_mode:
                cb.setEnabled(True)
            else:
                cb.setChecked(False)
                cb.setEnabled(False)

    # ── selection helpers ──────────────────────────────────────────────────

    def _trigger_select_all(self) -> None:
        all_checked = bool(self._pairs) and all(cb.isChecked() for _, cb in self._pairs)
        for _, cb in self._pairs:
            cb.setChecked(not all_checked)

    def _trigger_subgroup_select(self, target: str) -> None:
        pairs = [(c, cb) for c, cb in self._pairs
                 if c.is_merged and (c.merged_into or "main") == target]
        all_checked = bool(pairs) and all(cb.isChecked() for _, cb in pairs)
        for _, cb in pairs:
            cb.setChecked(not all_checked)

    def _trigger_stale_select(self) -> None:
        pairs = [(c, cb) for c, cb in self._pairs if c.is_stale and not c.is_merged]
        all_checked = bool(pairs) and all(cb.isChecked() for _, cb in pairs)
        for _, cb in pairs:
            cb.setChecked(not all_checked)

    def _refresh_button_labels(self) -> None:
        if self._global_btn:
            all_checked = bool(self._pairs) and all(cb.isChecked() for _, cb in self._pairs)
            self._global_btn.setText("Deselect All" if all_checked else "Select All")
        for target, btn in self._subgroup_btns.items():
            pairs = [(c, cb) for c, cb in self._pairs
                     if c.is_merged and (c.merged_into or "main") == target]
            all_checked = bool(pairs) and all(cb.isChecked() for _, cb in pairs)
            btn.setText("Deselect all" if all_checked else "Select all")
        if self._stale_btn is not None:
            pairs = [(c, cb) for c, cb in self._pairs if c.is_stale and not c.is_merged]
            all_checked = bool(pairs) and all(cb.isChecked() for _, cb in pairs)
            self._stale_btn.setText("Deselect all" if all_checked else "Select all")

    # ── delete ─────────────────────────────────────────────────────────────

    def _trigger_delete(self) -> None:
        selected = [c for c, cb in self._pairs if cb.isChecked()]
        if self._admin_mode:
            selected += [c for c, cb in self._protected_pairs if cb.isChecked()]
        if not selected:
            return
        repo_path = self._repo_combo.currentData()
        self._vm.delete_cleanup_selection(repo_path=repo_path, candidates=selected)
        self._load_and_render(repo_path)
