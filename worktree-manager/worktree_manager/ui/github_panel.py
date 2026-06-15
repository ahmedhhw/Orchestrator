import logging
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QApplication, QCheckBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices

from worktree_manager.github_vm import GitHubViewModel, TokenState
from worktree_manager.github_models import PullRequest
from worktree_manager.github_search import filter_prs, group_and_filter
from worktree_manager.ui.repo_settings_dialog import RepoSettingsDialog
from worktree_manager.ui.filterable_combo import FilterableComboBox


def _current_git_branch(repo_path: str) -> str:
    cwd = repo_path if repo_path and Path(repo_path).is_dir() else None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True, text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception as e:
        raise RuntimeError(f"Failed to get current branch: {e}") from e


def _github_api_base(repo_path: str) -> str:
    """Return 'https://api.github.com/repos/{owner}/{repo}' for the cwd's origin remote."""
    import re
    cwd = repo_path if repo_path and Path(repo_path).is_dir() else None
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd, capture_output=True, text=True,
        )
        remote = result.stdout.strip() if result.returncode == 0 else ""
    except Exception as e:
        raise RuntimeError(f"Failed to get git remote URL: {e}") from e
    ssh = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", remote)
    if ssh:
        return f"https://api.github.com/repos/{ssh.group(1)}/{ssh.group(2)}"
    from urllib.parse import urlparse
    parsed = urlparse(remote)
    parts = parsed.path.strip("/").split("/")
    if len(parts) >= 2:
        owner, repo = parts[0], parts[1].removesuffix(".git")
        return f"https://api.github.com/repos/{owner}/{repo}"
    return ""


class GitHubPanel(QWidget):
    def __init__(self, vm: GitHubViewModel, parent=None):
        super().__init__(parent)
        self._vm = vm

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(12, 8, 12, 8)
        title = QLabel("⬡  Pull Requests")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)
        header.addStretch(1)

        self._header_controls_widget = QWidget()
        ctrl_layout = QHBoxLayout(self._header_controls_widget)
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(6)

        self._notif_btn = QPushButton()
        self._notif_btn.setCheckable(True)
        self._notif_btn.setFixedWidth(36)
        enabled = bool(vm._store.get_ui_pref("github_notifications_enabled", True))
        self._notif_btn.setChecked(enabled)
        self._update_notif_btn()
        self._notif_btn.toggled.connect(self._on_notif_toggled)
        ctrl_layout.addWidget(self._notif_btn)

        interval = vm._store.get_github_poll_interval()
        self._poll_btn = QPushButton(f"↻ {interval}s")
        self._poll_btn.setFixedWidth(60)
        self._poll_btn.clicked.connect(self._toggle_polling)
        ctrl_layout.addWidget(self._poll_btn)

        self._token_rotate_btn = QPushButton("⚿ Token")
        self._token_rotate_btn.setFixedWidth(80)
        self._token_rotate_btn.clicked.connect(self._toggle_token_form)
        ctrl_layout.addWidget(self._token_rotate_btn)

        header.addWidget(self._header_controls_widget)
        outer.addLayout(header)

        # ── inline token rotation form (hidden by default) ─────────────────
        self._token_rotate_widget = QWidget()
        rot_layout = QHBoxLayout(self._token_rotate_widget)
        rot_layout.setContentsMargins(12, 4, 12, 4)
        self._token_rotate_input = QLineEdit()
        self._token_rotate_input.setPlaceholderText("New token…")
        self._token_rotate_input.setEchoMode(QLineEdit.Password)
        rot_save = QPushButton("Save")
        rot_save.clicked.connect(self._save_rotated_token)
        rot_cancel = QPushButton("Cancel")
        rot_cancel.clicked.connect(lambda: self._token_rotate_widget.hide())
        rot_layout.addWidget(self._token_rotate_input, 1)
        rot_layout.addWidget(rot_save)
        rot_layout.addWidget(rot_cancel)
        self._token_rotate_widget.hide()
        outer.addWidget(self._token_rotate_widget)

        # ── main stack: token-setup vs tab content ─────────────────────────
        self._main_stack = QStackedWidget()
        outer.addWidget(self._main_stack, 1)

        # Token setup / expired page
        self._token_setup_widget = QWidget()
        setup_layout = QVBoxLayout(self._token_setup_widget)
        setup_layout.setContentsMargins(24, 24, 24, 24)
        self._token_status_label = QLabel()
        setup_layout.addWidget(self._token_status_label)
        self._token_input = QLineEdit()
        self._token_input.setPlaceholderText("GitHub Personal Access Token")
        self._token_input.setEchoMode(QLineEdit.Password)
        setup_layout.addWidget(self._token_input)
        setup_layout.addWidget(QLabel("Needs: repo, read:org scopes"))
        self._save_token_btn = QPushButton("Save Token")
        self._save_token_btn.clicked.connect(self._on_save_token)
        setup_layout.addWidget(self._save_token_btn)
        setup_layout.addStretch(1)
        self._main_stack.addWidget(self._token_setup_widget)

        # Tab content page
        self._tab_content_widget = QWidget()
        tab_outer = QVBoxLayout(self._tab_content_widget)
        tab_outer.setContentsMargins(0, 0, 0, 0)
        self._tabs = QTabWidget()
        tab_outer.addWidget(self._tabs)
        self._main_stack.addWidget(self._tab_content_widget)

        # ── My PRs tab ─────────────────────────────────────────────────────
        my_prs_widget = QWidget()
        my_prs_layout = QVBoxLayout(my_prs_widget)
        my_prs_layout.setContentsMargins(0, 0, 0, 0)

        # list/detail stack within My PRs
        self._my_prs_stack = QStackedWidget()
        my_prs_layout.addWidget(self._my_prs_stack)

        self._pr_list_widget = QWidget()
        pr_list_layout = QVBoxLayout(self._pr_list_widget)
        pr_list_layout.setContentsMargins(0, 0, 0, 0)
        self._pr_error_label = QLabel()
        self._pr_error_label.setStyleSheet("color: red; padding: 8px;")
        self._pr_error_label.setWordWrap(True)
        self._pr_error_label.hide()
        pr_list_layout.addWidget(self._pr_error_label)
        self._loading_label = QLabel("⏳ Loading pull requests…")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.hide()
        pr_list_layout.addWidget(self._loading_label)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search PRs…")
        self._search_edit.textChanged.connect(self._on_search_changed)
        self._search_edit.hide()
        pr_list_layout.addWidget(self._search_edit)

        self._no_match_label = QLabel()
        self._no_match_label.setStyleSheet("color: gray; padding: 8px;")
        self._no_match_label.setAlignment(Qt.AlignCenter)
        self._no_match_label.hide()
        pr_list_layout.addWidget(self._no_match_label)

        self._pr_list = QListWidget()
        self._pr_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._pr_list.customContextMenuRequested.connect(self._on_pr_list_context_menu)
        pr_list_layout.addWidget(self._pr_list)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(8, 4, 8, 4)
        self._fetch_status_label = QLabel("Scanning GitHub for repos with your open PRs…")
        self._fetch_status_label.setStyleSheet("color: gray; font-size: 11px;")
        self._fetch_status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        footer_layout.addWidget(self._fetch_status_label, 1)
        self._rescan_btn = QPushButton("↺ Rescan")
        self._rescan_btn.setFixedWidth(80)
        self._rescan_btn.clicked.connect(vm.rescan_repos)
        footer_layout.addWidget(self._rescan_btn)
        pr_list_layout.addLayout(footer_layout)

        self._my_prs_stack.addWidget(self._pr_list_widget)

        self._pr_detail_widget = QWidget()
        detail_layout = QVBoxLayout(self._pr_detail_widget)
        detail_layout.setContentsMargins(12, 8, 12, 8)

        self._back_btn = QPushButton("← Back")
        self._back_btn.clicked.connect(self._on_back)
        detail_layout.addWidget(self._back_btn)

        detail_header = QHBoxLayout()
        self._detail_title_label = QLabel()
        self._detail_title_label.setStyleSheet("font-weight: bold;")
        self._detail_title_label.setWordWrap(True)
        detail_header.addWidget(self._detail_title_label, 1)
        self._copy_url_btn = QPushButton("⧉ Copy URL")
        self._copy_url_btn.setFixedWidth(90)
        self._copy_url_conn = None
        detail_header.addWidget(self._copy_url_btn)
        self._open_url_btn = QPushButton("↗ Open")
        self._open_url_btn.setFixedWidth(70)
        self._open_url_conn = None
        detail_header.addWidget(self._open_url_btn)
        detail_layout.addLayout(detail_header)

        checks_header = QHBoxLayout()
        checks_header.addWidget(QLabel("CI Checks"))
        checks_header.addStretch(1)
        self._retry_failed_btn = QPushButton("↺ Re-try failed")
        self._retry_failed_btn.setToolTip("Re-run only the failed CI jobs")
        self._retry_failed_btn.hide()
        self._retry_failed_conn = None
        checks_header.addWidget(self._retry_failed_btn)
        self._retry_all_btn = QPushButton("↺ Re-try all")
        self._retry_all_btn.setToolTip("Re-run all CI checks")
        self._retry_all_btn.hide()
        self._retry_all_conn = None
        checks_header.addWidget(self._retry_all_btn)
        detail_layout.addLayout(checks_header)
        self._rerun_status_label = QLabel()
        self._rerun_status_label.setStyleSheet("color: gray; font-size: 11px;")
        self._rerun_status_label.hide()
        detail_layout.addWidget(self._rerun_status_label)
        self._checks_list = QListWidget()
        self._checks_list.setMaximumHeight(120)
        detail_layout.addWidget(self._checks_list)

        detail_layout.addWidget(QLabel("Reviews"))
        self._reviews_list = QListWidget()
        self._reviews_list.setMaximumHeight(80)
        detail_layout.addWidget(self._reviews_list)

        detail_layout.addWidget(QLabel("Comments"))
        self._comments_list = QListWidget()
        self._comments_list.setMaximumHeight(120)
        detail_layout.addWidget(self._comments_list)

        self._mergeability_label = QLabel()
        detail_layout.addWidget(self._mergeability_label)

        self._merge_status_label = QLabel()
        detail_layout.addWidget(self._merge_status_label)

        merge_row = QHBoxLayout()
        self._squash_checkbox = QCheckBox("Squash and merge")
        self._squash_checkbox.setChecked(True)
        self._squash_checkbox.hide()
        merge_row.addWidget(self._squash_checkbox)
        merge_row.addStretch(1)
        self._merge_btn = QPushButton("Merge PR")
        self._merge_btn.hide()
        self._merge_btn_conn = None
        merge_row.addWidget(self._merge_btn)
        detail_layout.addLayout(merge_row)

        self._merge_error_label = QLabel()
        self._merge_error_label.setStyleSheet("color: red;")
        self._merge_error_label.setWordWrap(True)
        self._merge_error_label.hide()
        detail_layout.addWidget(self._merge_error_label)

        detail_layout.addStretch(1)

        self._my_prs_stack.addWidget(self._pr_detail_widget)
        self._tabs.addTab(my_prs_widget, "My PRs")

        # ── Open PR tab ─────────────────────────────────────────────────────
        open_pr_widget = QWidget()
        open_pr_layout = QVBoxLayout(open_pr_widget)
        open_pr_layout.setContentsMargins(12, 12, 12, 12)

        form_layout = open_pr_layout

        form_layout.addWidget(QLabel("Repo:"))
        self._repo_combo = FilterableComboBox()
        self._repo_combo.currentIndexChanged.connect(self._on_repo_changed)
        form_layout.addWidget(self._repo_combo)

        self._open_pr_no_remote_label = QLabel(
            "⚠ No remote branches found."
        )
        self._open_pr_no_remote_label.setStyleSheet("color: red;")
        self._open_pr_no_remote_label.setWordWrap(True)
        self._open_pr_no_remote_label.hide()
        form_layout.addWidget(self._open_pr_no_remote_label)

        form_layout.addWidget(QLabel("Branch:"))
        self._head_branch_combo = FilterableComboBox()
        self._head_branch_combo.currentIndexChanged.connect(self._on_head_branch_changed)
        form_layout.addWidget(self._head_branch_combo)

        form_layout.addWidget(QLabel("Title:"))
        self._pr_title_edit = QLineEdit()
        form_layout.addWidget(self._pr_title_edit)

        form_layout.addWidget(QLabel("Base branch:"))
        self._base_branch_combo = FilterableComboBox()
        form_layout.addWidget(self._base_branch_combo)

        form_layout.addWidget(QLabel("Description:"))
        self._description_edit = QTextEdit()
        self._description_edit.setMaximumHeight(120)
        form_layout.addWidget(self._description_edit)

        self._draft_checkbox = QCheckBox("Draft PR")
        form_layout.addWidget(self._draft_checkbox)

        self._push_open_btn = QPushButton("Push && Open PR")
        self._push_open_btn.clicked.connect(self._on_push_open_pr)
        form_layout.addWidget(self._push_open_btn)

        self._open_pr_error_label = QLabel()
        self._open_pr_error_label.setStyleSheet("color: red;")
        self._open_pr_error_label.hide()
        form_layout.addWidget(self._open_pr_error_label)
        form_layout.addStretch(1)

        self._tabs.addTab(open_pr_widget, "Open PR")

        # ── connect VM signals ──────────────────────────────────────────────
        vm.loading_started.connect(self._on_loading_started)
        vm.prs_updated.connect(self._on_prs_updated)
        vm.pr_detail_updated.connect(self._on_pr_detail_updated)
        vm.token_state_changed.connect(self._apply_token_state)
        vm.refresh_error.connect(self._on_refresh_error)
        vm.fetch_status_changed.connect(self._fetch_status_label.setText)

        self._repo_display_map: dict[str, str] = {}
        self._apply_token_state()
        self._populate_open_pr_form()
        if vm.token_state == TokenState.CONFIGURED:
            self._pr_list.hide()
            self._loading_label.show()

    # ── token state ────────────────────────────────────────────────────────────

    def _apply_token_state(self):
        state = self._vm.token_state
        if state == TokenState.MISSING:
            self._token_status_label.setText("GitHub token not configured.")
            self._save_token_btn.setText("Save Token")
            self._main_stack.setCurrentWidget(self._token_setup_widget)
            self._header_controls_widget.hide()
        elif state == TokenState.EXPIRED:
            self._token_status_label.setText("⚠ Token expired or invalid.")
            self._save_token_btn.setText("Update Token")
            self._main_stack.setCurrentWidget(self._token_setup_widget)
            self._header_controls_widget.hide()
        else:
            self._main_stack.setCurrentWidget(self._tab_content_widget)
            self._header_controls_widget.show()

    def _on_save_token(self):
        token = self._token_input.text().strip()
        if token:
            self._vm.save_token(token)
            self._token_input.clear()
            self._vm.total_fetch()

    def _toggle_token_form(self):
        visible = self._token_rotate_widget.isVisible()
        self._token_rotate_widget.setVisible(not visible)

    def _save_rotated_token(self):
        token = self._token_rotate_input.text().strip()
        if token:
            self._vm.save_token(token)
            self._token_rotate_input.clear()
            self._token_rotate_widget.hide()
            self._vm.total_fetch()

    # ── poll toggle ────────────────────────────────────────────────────────────

    def _toggle_polling(self):
        interval = self._vm._store.get_github_poll_interval()
        if self._vm.polling_active:
            self._vm.pause_polling()
            self._poll_btn.setText(f"⏸ {interval}s")
        else:
            self._vm.resume_polling()
            self._poll_btn.setText(f"↻ {interval}s")

    def _on_notif_toggled(self, checked: bool) -> None:
        self._vm._store.set_ui_pref("github_notifications_enabled", bool(checked))
        self._update_notif_btn()

    def _update_notif_btn(self) -> None:
        on = self._notif_btn.isChecked()
        self._notif_btn.setText("🔔" if on else "🔕")
        self._notif_btn.setToolTip(
            "Notifications: On — click to mute" if on
            else "Notifications: Off — click to enable"
        )

    # ── My PRs list ────────────────────────────────────────────────────────────

    def _on_loading_started(self):
        self._pr_list.hide()
        self._loading_label.show()

    def _on_refresh_error(self, message: str):
        self._loading_label.hide()
        self._pr_list.show()
        self._pr_error_label.setText(message)
        self._pr_error_label.show()

    def _on_prs_updated(self):
        self._loading_label.hide()
        self._pr_error_label.hide()
        self._render_pr_list()

    def _on_search_changed(self, text: str):
        self._render_pr_list()

    def _render_pr_list(self):
        self._pr_list.clear()
        self._no_match_label.hide()

        all_prs = self._vm.prs

        if not all_prs:
            self._search_edit.hide()
            self._pr_list.show()
            return

        self._search_edit.show()
        needle = self._search_edit.text()

        store = self._vm._store
        collapsed_repos = {
            repo for repo in {f"{p.owner}/{p.repo}" for p in all_prs}
            if store.get_repo_collapsed(repo)
        }

        groups = group_and_filter(all_prs, needle, collapsed_repos)

        if not groups:
            self._pr_list.hide()
            self._no_match_label.setText(f'No pull requests match "{needle}"')
            self._no_match_label.show()
            return

        self._pr_list.show()
        for group in groups:
            self._add_repo_header(group, store)
            if not group.collapsed:
                for pr in group.prs:
                    self._add_pr_row(pr)

    def _add_repo_header(self, group, store) -> None:
        glyph = "▸" if group.collapsed else "▾"
        repo = group.repo

        header_widget = QWidget()
        header_widget.setStyleSheet("background: palette(midlight);")
        h_layout = QHBoxLayout(header_widget)
        h_layout.setContentsMargins(8, 4, 8, 4)

        name_btn = QPushButton(f"{glyph}  {repo}  ({group.count})")
        name_btn.setFlat(True)
        name_btn.setStyleSheet("font-weight: bold; text-align: left;")
        name_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        name_btn.clicked.connect(lambda checked=False, r=repo: self._toggle_repo_collapsed(r, store))
        h_layout.addWidget(name_btn, 1)

        gear_btn = QPushButton("⚙")
        gear_btn.setFixedWidth(32)
        gear_btn.setToolTip(f"Settings for {repo}")
        gear_btn.setStyleSheet("QPushButton { background: palette(button); border: 1px solid palette(mid); border-radius: 4px; padding: 2px; }")
        gear_btn.clicked.connect(lambda checked=False, r=repo: self._open_repo_settings(r, store))
        h_layout.addWidget(gear_btn)

        item = QListWidgetItem()
        item.setFlags(Qt.ItemIsEnabled)  # not selectable
        item.setSizeHint(header_widget.sizeHint().__class__(0, 34))
        self._pr_list.addItem(item)
        self._pr_list.setItemWidget(item, header_widget)

    def _toggle_repo_collapsed(self, repo: str, store) -> None:
        store.set_repo_collapsed(repo, not store.get_repo_collapsed(repo))
        self._render_pr_list()

    def _open_repo_settings(self, repo: str, store) -> None:
        discovered = sorted({
            c.name for p in self._vm.prs
            if f"{p.owner}/{p.repo}" == repo
            for c in p.checks
        })
        dlg = RepoSettingsDialog(repo, store, discovered, parent=self)
        dlg.exec()
        self._render_pr_list()

    def _add_pr_row(self, pr: PullRequest) -> None:
        muted = self._vm.muted_checks_for(f"{pr.owner}/{pr.repo}")
        badge = self._ci_badge(pr, muted)
        unread = self._vm.unread_comment_count(pr)
        badge_prefix = f"🔴 {unread} new  " if unread > 0 else ""
        merge_badge = self._mergeable_badge(pr)
        label_text = (f"#{pr.number}  {pr.title}   {badge_prefix}{badge}\n"
                      f"{pr.head_branch} → {pr.base_branch}    {merge_badge}")

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel(label_text)
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout.addWidget(lbl, 1)
        view_btn = QPushButton("↗ View")
        view_btn.setFixedWidth(64)
        view_btn.clicked.connect(lambda checked=False, p=pr: self._vm.select_pr(p))
        row_layout.addWidget(view_btn)

        item = QListWidgetItem()
        item.setData(Qt.UserRole, pr.pr_key)
        item.setSizeHint(row_widget.sizeHint().__class__(0, 48))
        self._pr_list.addItem(item)
        self._pr_list.setItemWidget(item, row_widget)


    @staticmethod
    def _mergeable_badge(pr: PullRequest) -> str:
        return {
            "mergeable": "🟢 Mergeable",
            "conflicts": "🔴 Conflicts",
            "behind":    "🟠 Behind base",
            "blocked":   "🔒 Blocked",
            "checking":  "⚪ Checking mergeability…",
        }.get(pr.mergeability(), "⚪ Checking mergeability…")

    def _ci_badge(self, pr: PullRequest, muted: set | None = None) -> str:
        muted = muted or set()
        status, ignored = pr.ci_status_summary(muted)
        base = {
            "running": "⏳ checks running",
            "failed":  "❌ checks failed",
            "passed":  "✅ checks passed",
        }.get(status, "– no checks")
        if ignored and status != "failed":
            return f"{base} · {ignored} ignored"
        return base

    def _on_pr_list_context_menu(self, pos) -> None:
        item = self._pr_list.itemAt(pos)
        if item is None:
            return
        pr_key = item.data(Qt.UserRole)
        self._show_pr_context_menu(pr_key, item)

    def _show_pr_context_menu(self, pr_key: tuple, item: QListWidgetItem) -> None:
        pr = next((p for p in self._vm.prs if p.pr_key == pr_key), None)
        if pr is None:
            return
        log.debug(
            "context_menu PR #%d: mergeable=%r is_ready=%r",
            pr.number, pr.mergeable, pr.is_ready_to_merge(),
        )
        menu = QMenu(self)
        menu.addAction("↗ Open in browser")
        menu.addAction("↗ View details")
        if pr.is_ready_to_merge():
            menu.addAction("✓ Merge (squash)")
        menu.addAction("⧉ Copy URL")
        failed_run_ids = pr.failed_actions_run_ids()
        has_checks = bool(pr.checks)
        if failed_run_ids or has_checks:
            menu.addSeparator()
        if failed_run_ids:
            menu.addAction("↺ Re-try failed CIs")
        if has_checks:
            menu.addAction("↺ Re-try all CIs")
        action = menu.exec(QCursor.pos())
        if action is None:
            return
        text = action.text()
        if text == "↗ Open in browser":
            QDesktopServices.openUrl(QUrl(pr.html_url))
        elif text == "↗ View details":
            self._vm.select_pr(pr)
        elif text == "✓ Merge (squash)":
            self._vm.merge_pr(pr, squash=True)
        elif text == "⧉ Copy URL":
            QApplication.clipboard().setText(pr.html_url)
        elif text == "↺ Re-try failed CIs":
            try:
                self._vm.retry_failed_cis(pr)
            except Exception as exc:
                self._on_refresh_error(f"⚠ Re-run failed: {exc}")
        elif text == "↺ Re-try all CIs":
            try:
                self._vm.retry_all_cis(pr)
            except Exception as exc:
                self._on_refresh_error(f"⚠ Re-run failed: {exc}")

    def _on_pr_detail_updated(self):
        pr = self._vm.selected_pr
        if pr is None:
            self._my_prs_stack.setCurrentWidget(self._pr_list_widget)
            return
        self._my_prs_stack.setCurrentWidget(self._pr_detail_widget)
        self._vm.mark_pr_comments_seen(pr)
        self._detail_title_label.setText(f"#{pr.number}  {pr.title}\n{pr.head_branch} → {pr.base_branch}")

        if self._copy_url_conn is not None:
            self._copy_url_btn.clicked.disconnect(self._copy_url_conn)
        self._copy_url_conn = self._copy_url_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(pr.html_url)
        )
        if self._open_url_conn is not None:
            self._open_url_btn.clicked.disconnect(self._open_url_conn)
        self._open_url_conn = self._open_url_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(pr.html_url))
        )

        self._checks_list.clear()
        for c in pr.checks:
            conclusion = c.conclusion or "running"
            badge = {"success": "✅", "failure": "❌"}.get(conclusion, "⏳")
            self._checks_list.addItem(f"● {c.name}   {badge} {conclusion}")

        self._rerun_status_label.hide()

        failed_run_ids = pr.failed_actions_run_ids()
        if failed_run_ids:
            self._retry_failed_btn.show()
            if self._retry_failed_conn is not None:
                self._retry_failed_btn.clicked.disconnect(self._retry_failed_conn)
            self._retry_failed_conn = self._retry_failed_btn.clicked.connect(
                lambda checked=False, p=pr: self._on_retry_failed(p)
            )
        else:
            self._retry_failed_btn.hide()

        if pr.checks:
            self._retry_all_btn.show()
            if self._retry_all_conn is not None:
                self._retry_all_btn.clicked.disconnect(self._retry_all_conn)
            self._retry_all_conn = self._retry_all_btn.clicked.connect(
                lambda checked=False, p=pr: self._on_retry_all(p)
            )
        else:
            self._retry_all_btn.hide()

        self._reviews_list.clear()
        if pr.reviews:
            for r in pr.reviews:
                badge = "✅" if r.state == "APPROVED" else "🔄"
                self._reviews_list.addItem(f"{badge} {r.author} {r.state.lower()}")
        else:
            self._reviews_list.addItem("No reviews yet.")

        self._comments_list.clear()
        if pr.comments:
            for c in pr.comments:
                self._comments_list.addItem(f'{c.author}: "{c.body}"')
        else:
            self._comments_list.addItem("No comments.")

        self._mergeability_label.setText("Mergeability:  " + self._mergeable_badge(pr))

        s = pr.ci_status()
        if s == "running":
            self._merge_status_label.setText("⏳ Checks running — not ready to merge")
        elif s == "failed":
            self._merge_status_label.setText("❌ Checks failed")
        else:
            self._merge_status_label.setText("")

        self._merge_error_label.hide()
        log.debug(
            "pr_detail_updated PR #%d: mergeable=%r is_ready=%r",
            pr.number, pr.mergeable, pr.is_ready_to_merge(),
        )
        if pr.is_ready_to_merge():
            self._merge_status_label.setText("✅ Ready to merge")
            self._squash_checkbox.show()
            self._merge_btn.show()
            if self._merge_btn_conn is not None:
                self._merge_btn.clicked.disconnect(self._merge_btn_conn)
            self._merge_btn_conn = self._merge_btn.clicked.connect(lambda checked=False, p=pr: self._on_merge_pr(p))
        else:
            self._squash_checkbox.hide()
            self._merge_btn.hide()

    def _on_retry_failed(self, pr: PullRequest) -> None:
        try:
            note = self._vm.retry_failed_cis(pr)
        except Exception as exc:
            self._show_rerun_error(exc)
            return
        msg = "⏳ Re-running failed checks…"
        if note:
            msg += "  " + note
        self._show_rerun_status(msg)

    def _on_retry_all(self, pr: PullRequest) -> None:
        try:
            self._vm.retry_all_cis(pr)
        except Exception as exc:
            self._show_rerun_error(exc)
            return
        self._show_rerun_status("⏳ Re-running all checks…")

    def _show_rerun_status(self, msg: str) -> None:
        self._rerun_status_label.setStyleSheet("color: gray; font-size: 11px;")
        self._rerun_status_label.setText(msg)
        self._rerun_status_label.show()

    def _show_rerun_error(self, exc: Exception) -> None:
        self._rerun_status_label.setStyleSheet("color: red; font-size: 11px;")
        self._rerun_status_label.setText(f"⚠ Re-run failed: {exc}")
        self._rerun_status_label.show()

    def _on_back(self):
        self._vm.deselect_pr()
        self._my_prs_stack.setCurrentWidget(self._pr_list_widget)

    def _on_merge_pr(self, pr: PullRequest) -> None:
        squash = self._squash_checkbox.isChecked()
        self._merge_btn.setEnabled(False)
        self._merge_btn.setText("Merging…")
        self._merge_error_label.hide()
        try:
            self._vm.merge_pr(pr, squash=squash)
            self._squash_checkbox.hide()
            self._merge_btn.hide()
            self._merge_status_label.setStyleSheet("color: green; font-weight: bold;")
            for remaining in range(5, 0, -1):
                self._merge_status_label.setText(f"✅ Merged — refreshing in {remaining}s…")
                QApplication.processEvents()
                time.sleep(1)
            self._vm.total_fetch()
            self._on_back()
        except Exception as exc:
            self._merge_error_label.setText(str(exc))
            self._merge_error_label.show()
            self._merge_btn.setEnabled(True)
            self._merge_btn.setText("Merge PR")

    # ── Open PR form ───────────────────────────────────────────────────────────

    def _current_repo_path(self) -> str:
        """Resolve the combo's current display name back to the full repo path."""
        display = self._repo_combo.currentText()
        return self._repo_display_map.get(display, display)

    def _populate_open_pr_form(self):
        self._repo_display_map: dict[str, str] = self._vm.list_open_pr_repos_display()
        self._repo_combo.blockSignals(True)
        self._repo_combo.clear()
        for display_name in self._repo_display_map:
            self._repo_combo.addItem(display_name)
        self._repo_combo.blockSignals(False)

        # Load branches for the first repo (triggers title/base update)
        if self._repo_display_map:
            first_path = next(iter(self._repo_display_map.values()))
            self._load_branches_for_repo(first_path)
        else:
            self._head_branch_combo.clear()
            self._base_branch_combo.clear()
            self._pr_title_edit.setText("")

        # Pre-fill description from PR template of the selected repo
        self._prefill_pr_template()

    def _load_branches_for_repo(self, repo_path: str) -> None:
        remote_branches = self._vm.list_remote_branches_for_repo(repo_path)

        has_remote = bool(remote_branches)
        self._open_pr_no_remote_label.setVisible(not has_remote)
        for w in (
            self._head_branch_combo,
            self._pr_title_edit,
            self._base_branch_combo,
            self._description_edit,
            self._draft_checkbox,
            self._push_open_btn,
        ):
            w.setEnabled(has_remote)

        local_branches = self._vm.list_branches_for_repo(repo_path)
        branches_with_prs = {p.head_branch for p in self._vm.prs}
        available_branches = [b for b in local_branches if b not in branches_with_prs]

        self._head_branch_combo.blockSignals(True)
        self._head_branch_combo.clear()
        for b in available_branches:
            self._head_branch_combo.addItem(b)
        self._head_branch_combo.blockSignals(False)

        self._base_branch_combo.clear()
        for b in remote_branches:
            self._base_branch_combo.addItem(b)

        initial_branch = available_branches[0] if available_branches else ""
        self._set_base_branch_for_head(initial_branch, remote_branches)

        if available_branches:
            self._update_title_from_branch(available_branches[0])

    def _on_repo_changed(self, index: int) -> None:
        repo_path = self._current_repo_path()
        if repo_path:
            self._load_branches_for_repo(repo_path)
            self._prefill_pr_template()

    def _on_head_branch_changed(self, index: int) -> None:
        branch = self._head_branch_combo.currentText()
        if branch:
            self._update_title_from_branch(branch)
            remote_branches = [
                self._base_branch_combo.itemText(i)
                for i in range(self._base_branch_combo.count())
            ]
            repo_path = self._current_repo_path()
            self._set_base_branch_for_head(branch, remote_branches, repo_path=repo_path)

    def _set_base_branch_for_head(
        self, branch: str, remote_branches: list[str], repo_path: str | None = None
    ) -> None:
        if not repo_path:
            repo_path = self._current_repo_path()
        parent = None
        if branch and repo_path:
            parent = self._vm.get_parent_branch_for_repo(repo_path, branch, remote_branches)
        if parent:
            self._base_branch_combo.setCurrentText(parent)
        else:
            preferred = next((b for b in remote_branches if b in ("main", "master")), None)
            if preferred:
                self._base_branch_combo.setCurrentText(preferred)

    def _update_title_from_branch(self, branch: str) -> None:
        title = branch.split("/")[-1].replace("-", " ").replace("_", " ").title() if branch else ""
        self._pr_title_edit.setText(title)

    def _prefill_pr_template(self) -> None:
        repo_path = self._current_repo_path()
        if repo_path:
            template_path = Path(repo_path) / ".github" / "pull_request_template.md"
            if template_path.exists():
                self._description_edit.setPlainText(template_path.read_text())


    def _on_push_open_pr(self):
        title = self._pr_title_edit.text().strip()
        body = self._description_edit.toPlainText()
        base = self._base_branch_combo.currentText()
        draft = self._draft_checkbox.isChecked()
        repo_path = self._current_repo_path()
        branch = self._head_branch_combo.currentText()

        self._open_pr_error_label.hide()
        self._push_open_btn.setEnabled(False)
        self._push_open_btn.setText("Pushing…")

        try:
            svc = self._vm._svc
            if svc is None:
                raise RuntimeError("GitHub service not configured")
            if not repo_path:
                raise RuntimeError("No repo selected")
            if not branch:
                raise RuntimeError("No branch selected")
            repo_base_url = _github_api_base(repo_path)
            if not repo_base_url:
                raise RuntimeError("Could not detect GitHub remote for this directory")
            svc.push_branch(branch, repo_path=repo_path)
            svc.create_pull_request(title=title, body=body, base=base, branch=branch, draft=draft, repo_base_url=repo_base_url)
            delay = 2
            for remaining in range(delay, 0, -1):
                self._push_open_btn.setText(f"Sleeping {remaining}s before fetching PRs…")
                QApplication.processEvents()
                time.sleep(1)
            self._vm.total_fetch()
            self._tabs.setCurrentIndex(0)
        except Exception as exc:
            self._open_pr_error_label.setText(str(exc))
            self._open_pr_error_label.show()
        finally:
            self._push_open_btn.setEnabled(True)
            self._push_open_btn.setText("Push & Open PR")
