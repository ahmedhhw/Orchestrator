import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
    QLabel, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from worktree_manager.ui.background_job import BackgroundJob
from worktree_manager.ui.cleanup_wizard import (
    _group_candidates, _merged_subgroups, _reason,
)
from worktree_manager.ui.inline_progress import InlineProgress


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

        # sync UI state
        self._sync_rows: list = []
        self._status_labels: dict = {}     # (repo_path, branch) -> QLabel
        self._error_btn_slots: dict = {}   # (repo_path, branch) -> QHBoxLayout
        self._sync_row_btns: dict = {}     # (repo_path, branch) -> QPushButton
        self._last_fetch_label: QLabel | None = None
        self._last_fetch_ts: int | None = None
        self._sync_loading: bool = False
        self._action_running: bool = False
        self._fetch_btn: QPushButton | None = None
        self._sync_all_btn: QPushButton | None = None
        self._sync_body_layout: QVBoxLayout | None = None
        self._sync_job: BackgroundJob | None = None

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

        # start on sync tab (highlight only — don't load data until explicitly shown)
        self._sync_btn.setChecked(True)

    # ── section switching ──────────────────────────────────────────────────

    def _switch_section(self, section: str) -> None:
        self._sync_btn.setChecked(section == "sync")
        self._cleanup_btn.setChecked(section == "cleanup")
        self._clear_content()
        if section == "sync":
            if self._vm is not None:
                self._build_sync_ui()
            else:
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
        self._status_labels = {}
        self._error_btn_slots = {}
        self._last_fetch_label = None

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

    def show_sync(self) -> None:
        """Switch to Sync from origin section."""
        self._switch_section("sync")

    def show_cleanup(self, repo_path: str | None) -> None:
        """Switch to Cleanup section, pre-select repo_path (None = all repos)."""
        self._current_repo_path = repo_path
        self._switch_section("cleanup")

    def refresh(self) -> None:
        """Reload the currently visible section."""
        if self._sync_btn.isChecked() and self._vm is not None and self._sync_body_layout is not None:
            self._start_sync_load()
        elif self._cleanup_btn.isChecked() and self._vm is not None:
            self._load_and_render(self._current_repo_path)

    # ── sync UI builder ────────────────────────────────────────────────────

    def _build_sync_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        # header row: title + Fetch all + Sync all
        header_row = QHBoxLayout()
        title = QLabel("Sync from origin")
        title.setStyleSheet("font-weight: bold;")
        header_row.addWidget(title)
        header_row.addStretch(1)
        self._fetch_btn = QPushButton("↻ Fetch all")
        self._fetch_btn.clicked.connect(self._trigger_fetch_all)
        header_row.addWidget(self._fetch_btn)
        self._sync_all_btn = QPushButton("⏬ Sync all")
        self._sync_all_btn.clicked.connect(self._trigger_sync_all)
        header_row.addWidget(self._sync_all_btn)
        layout.addLayout(header_row)

        # body area (holds InlineProgress while loading, then scroll+rows)
        self._sync_body_layout = QVBoxLayout()
        self._sync_body_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._sync_body_layout, 1)

        # last fetch footer
        self._last_fetch_label = QLabel("")
        self._last_fetch_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._last_fetch_label)

        self._content_area.addWidget(container)
        self._start_sync_load()

    def _clear_sync_body(self):
        while self._sync_body_layout.count():
            item = self._sync_body_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _set_sync_action_buttons_enabled(self, enabled: bool) -> None:
        if self._fetch_btn:
            self._fetch_btn.setEnabled(enabled)
        if self._sync_all_btn:
            self._sync_all_btn.setEnabled(enabled)

    def _start_sync_load(self):
        self._sync_loading = True
        self._action_running = False
        self._set_sync_action_buttons_enabled(False)
        self._status_labels = {}
        self._error_btn_slots = {}
        self._sync_row_btns = {}

        loader = InlineProgress()
        loader.start_determinate("Loading branches…", total=1)
        self._clear_sync_body()
        self._sync_body_layout.addWidget(loader)

        job = BackgroundJob(self)
        self._sync_job = job
        job.progress.connect(
            lambda cur, tot, lbl: loader.update(cur, lbl) if self._sync_loading else None
        )
        job.finished.connect(lambda rows: self._on_sync_loaded(rows))
        job.failed.connect(lambda exc: self._on_sync_failed(exc))
        job.start(self._vm.load_syncable_branches)

    def _on_sync_loaded(self, rows: list) -> None:
        self._sync_loading = False
        self._set_sync_action_buttons_enabled(True)
        self._clear_sync_body()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        list_container = QWidget()
        self._sync_list_layout = QVBoxLayout(list_container)
        self._sync_list_layout.setContentsMargins(0, 0, 0, 0)
        self._sync_list_layout.setSpacing(2)
        scroll.setWidget(list_container)
        self._sync_body_layout.addWidget(scroll)

        self._sync_rows = rows
        by_repo: dict[str, list] = {}
        for row in rows:
            by_repo.setdefault(row.repo_path, []).append(row)
        for repo_path, repo_rows in by_repo.items():
            repo_label = QLabel(f"▼ {os.path.basename(repo_path.rstrip('/'))}")
            repo_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
            self._sync_list_layout.addWidget(repo_label)
            for row in repo_rows:
                self._sync_list_layout.addWidget(self._make_branch_row_widget(row))
        self._sync_list_layout.addStretch(1)

    def _on_sync_failed(self, exc: Exception) -> None:
        self._sync_loading = False
        self._set_sync_action_buttons_enabled(True)
        self._clear_sync_body()

        error_widget = QWidget()
        err_layout = QVBoxLayout(error_widget)
        err_layout.setAlignment(Qt.AlignCenter)
        err_lbl = QLabel(f"⚠ Couldn't load branches.\n{exc}")
        err_lbl.setAlignment(Qt.AlignCenter)
        err_lbl.setStyleSheet("color: #c0392b;")
        err_layout.addWidget(err_lbl)
        retry_btn = QPushButton("Retry")
        retry_btn.setFixedWidth(80)
        retry_btn.clicked.connect(self._start_sync_load)
        err_layout.addWidget(retry_btn, 0, Qt.AlignCenter)
        self._sync_body_layout.addWidget(error_widget)

    def _render_sync_rows(self):
        while self._sync_list_layout.count():
            item = self._sync_list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._status_labels = {}

        rows = self._vm.load_syncable_branches()
        self._sync_rows = rows

        # group by repo
        by_repo: dict[str, list] = {}
        for row in rows:
            by_repo.setdefault(row.repo_path, []).append(row)

        for repo_path, repo_rows in by_repo.items():
            repo_label = QLabel(f"▼ {os.path.basename(repo_path.rstrip('/'))}")
            repo_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
            self._sync_list_layout.addWidget(repo_label)

            for row in repo_rows:
                self._sync_list_layout.addWidget(self._make_branch_row_widget(row))

        self._sync_list_layout.addStretch(1)

    def _make_branch_row_widget(self, row) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 2, 0, 2)
        layout.setSpacing(8)

        cb = QCheckBox()
        cb.setChecked(not row.excluded)
        cb.toggled.connect(
            lambda checked, rp=row.repo_path, br=row.branch:
                self._vm.set_excluded(rp, br, not checked)
        )
        layout.addWidget(cb)

        name_lbl = QLabel(row.branch)
        name_lbl.setMinimumWidth(160)
        layout.addWidget(name_lbl)

        if row.has_upstream:
            if row.behind > 0:
                badge_text = f"{row.behind} behind"
            elif row.ahead > 0:
                badge_text = f"{row.ahead} ahead"
            else:
                badge_text = "up to date"
            status_lbl = QLabel(badge_text)
            status_lbl.setStyleSheet("color: gray;")
            status_lbl.setMinimumWidth(100)
            layout.addWidget(status_lbl)
            self._status_labels[(row.repo_path, row.branch)] = status_lbl
            self._error_btn_slots[(row.repo_path, row.branch)] = layout

            sync_row_btn = QPushButton("Sync")
            sync_row_btn.setFixedWidth(52)
            sync_row_btn.clicked.connect(
                lambda _=False, rp=row.repo_path, br=row.branch, wt=row.worktree_path:
                    self._trigger_sync_one(rp, br, wt)
            )
            layout.addWidget(sync_row_btn)
            self._sync_row_btns[(row.repo_path, row.branch)] = sync_row_btn
        else:
            no_up_lbl = QLabel("✗ no upstream")
            no_up_lbl.setStyleSheet("color: gray;")
            layout.addWidget(no_up_lbl)
            self._status_labels[(row.repo_path, row.branch)] = no_up_lbl

        layout.addStretch(1)
        return w

    def _trigger_fetch_all(self):
        if self._vm is None or self._action_running:
            return
        self._action_running = True
        self._set_sync_action_buttons_enabled(False)
        job = BackgroundJob(self)
        job.finished.connect(self._on_fetch_done)
        job.failed.connect(lambda exc: self._on_action_error(exc))
        job.start(self._vm.fetch_all)

    def _on_fetch_done(self, _results) -> None:
        self._action_running = False
        self._last_fetch_ts = int(time.time())
        if self._last_fetch_label is not None:
            self._last_fetch_label.setText("Last fetch: just now")
        self._set_sync_action_buttons_enabled(True)

    def _trigger_sync_all(self):
        if self._vm is None or self._action_running:
            return
        self._action_running = True
        self._set_sync_action_buttons_enabled(False)
        job = BackgroundJob(self)
        job.finished.connect(lambda results: self._on_sync_all_done(results))
        job.failed.connect(lambda exc: self._on_action_error(exc))
        job.start(self._vm.sync_included)

    def _on_sync_all_done(self, results) -> None:
        self._action_running = False
        self._set_sync_action_buttons_enabled(True)
        self._apply_sync_results(results)

    def _trigger_sync_one(self, repo_path: str, branch: str, worktree_path):
        if self._vm is None or self._action_running:
            return
        self._action_running = True
        key = (repo_path, branch)
        btn = self._sync_row_btns.get(key)
        if btn is not None:
            btn.setEnabled(False)

        # show mini indeterminate bar in the status cell
        status_lbl = self._status_labels.get(key)
        mini_bar = None
        if status_lbl is not None:
            from worktree_manager.ui.inline_progress import InlineProgress
            mini_bar = InlineProgress.mini()
            mini_bar.start_indeterminate("syncing…")
            parent_layout = status_lbl.parent().layout() if status_lbl.parent() else None
            if parent_layout is not None:
                idx = parent_layout.indexOf(status_lbl)
                status_lbl.setVisible(False)
                parent_layout.insertWidget(idx, mini_bar)

        job = BackgroundJob(self)
        job.finished.connect(
            lambda result, b=btn, mb=mini_bar, sl=status_lbl:
                self._on_sync_one_done(result, b, mb, sl)
        )
        job.failed.connect(lambda exc: self._on_action_error(exc, btn=btn))
        job.start(self._vm.sync_one, repo_path=repo_path, branch=branch,
                  worktree_path=worktree_path)

    def _on_sync_one_done(self, result, btn, mini_bar, status_lbl) -> None:
        self._action_running = False
        if mini_bar is not None:
            mini_bar.deleteLater()
        if status_lbl is not None:
            status_lbl.setVisible(True)
        if btn is not None:
            btn.setEnabled(True)
        self._apply_sync_results([result])

    def _on_action_error(self, exc: Exception, btn=None) -> None:
        self._action_running = False
        self._set_sync_action_buttons_enabled(True)
        if btn is not None:
            btn.setEnabled(True)

    def _apply_sync_results(self, results):
        _badge = {
            "up_to_date": "✓ up to date",
            "pulled": "✓ pulled",
            "dirty": "⚠ dirty — skipped",
            "non_ff": "✗ non-ff — manual fix",
            "error": "✗ error",
        }
        _needs_detail = {"non_ff", "error"}
        for result in results:
            lbl = self._status_labels.get((result.repo_path, result.branch))
            if lbl is None:
                continue
            text = _badge.get(result.status, result.status)
            if result.status == "pulled" and result.new_commits:
                text = f"✓ pulled ({result.new_commits} new)"
            lbl.setText(text)

            error_detail = getattr(result, "error", None)
            if result.status in _needs_detail and error_detail:
                lbl.setToolTip(error_detail.strip())
                row_layout = self._error_btn_slots.get((result.repo_path, result.branch))
                if row_layout is not None:
                    detail_btn = QPushButton("Details")
                    detail_btn.setToolTip("Show full error output")
                    detail_btn.setStyleSheet("color: #c0392b;")
                    captured = error_detail
                    branch = result.branch
                    detail_btn.clicked.connect(
                        lambda _=False, msg=captured, br=branch:
                            self._show_error_detail(br, msg)
                    )
                    row_layout.insertWidget(row_layout.count() - 1, detail_btn)

    def _show_error_detail(self, branch: str, error_text: str) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Sync error — {branch}")
        dlg.setMinimumWidth(520)
        layout = QVBoxLayout(dlg)
        header = QLabel(f"Git reported an error syncing <b>{branch}</b>:")
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)
        text_edit = QPlainTextEdit(error_text.strip())
        text_edit.setReadOnly(True)
        text_edit.setMinimumHeight(180)
        layout.addWidget(text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.exec()

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
