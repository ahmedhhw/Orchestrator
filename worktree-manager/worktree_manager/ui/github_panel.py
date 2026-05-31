import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from worktree_manager.github_vm import GitHubViewModel, TokenState
from worktree_manager.github_models import PullRequest


def _current_git_branch(repo_path: str) -> str:
    cwd = repo_path if repo_path and Path(repo_path).is_dir() else None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True, text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
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
        self._pr_list = QListWidget()
        self._pr_list.itemActivated.connect(self._on_pr_row_activated)
        pr_list_layout.addWidget(self._pr_list)
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
        detail_header.addWidget(self._copy_url_btn)
        self._open_url_btn = QPushButton("↗ Open")
        self._open_url_btn.setFixedWidth(70)
        detail_header.addWidget(self._open_url_btn)
        detail_layout.addLayout(detail_header)

        checks_header = QHBoxLayout()
        checks_header.addWidget(QLabel("CI Checks"))
        checks_header.addStretch(1)
        self._rerun_btn = QPushButton("↺ Re-run")
        self._rerun_btn.setFixedWidth(80)
        self._rerun_btn.hide()
        checks_header.addWidget(self._rerun_btn)
        detail_layout.addLayout(checks_header)
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

        self._merge_status_label = QLabel()
        detail_layout.addWidget(self._merge_status_label)
        detail_layout.addStretch(1)

        self._my_prs_stack.addWidget(self._pr_detail_widget)
        self._tabs.addTab(my_prs_widget, "My PRs")

        # ── Open PR tab ─────────────────────────────────────────────────────
        open_pr_widget = QWidget()
        open_pr_layout = QVBoxLayout(open_pr_widget)
        open_pr_layout.setContentsMargins(12, 12, 12, 12)

        self._open_pr_stack = QStackedWidget()

        # Form page
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self._branch_label = QLabel()
        form_layout.addWidget(self._branch_label)

        form_layout.addWidget(QLabel("Title:"))
        self._pr_title_edit = QLineEdit()
        form_layout.addWidget(self._pr_title_edit)

        form_layout.addWidget(QLabel("Base branch:"))
        self._base_branch_combo = QComboBox()
        form_layout.addWidget(self._base_branch_combo)

        form_layout.addWidget(QLabel("Description:"))
        self._description_edit = QTextEdit()
        self._description_edit.setMaximumHeight(120)
        form_layout.addWidget(self._description_edit)

        self._draft_checkbox = QCheckBox("Draft PR")
        form_layout.addWidget(self._draft_checkbox)

        self._push_open_btn = QPushButton("Push & Open PR")
        self._push_open_btn.clicked.connect(self._on_push_open_pr)
        form_layout.addWidget(self._push_open_btn)

        self._open_pr_error_label = QLabel()
        self._open_pr_error_label.setStyleSheet("color: red;")
        self._open_pr_error_label.hide()
        form_layout.addWidget(self._open_pr_error_label)
        form_layout.addStretch(1)
        self._open_pr_stack.addWidget(form_widget)

        # Existing PR page
        existing_pr_widget = QWidget()
        existing_layout = QVBoxLayout(existing_pr_widget)
        self._existing_pr_label = QLabel()
        self._existing_pr_label.setWordWrap(True)
        existing_layout.addWidget(self._existing_pr_label)
        view_in_my_prs_btn = QPushButton("View in My PRs")
        view_in_my_prs_btn.clicked.connect(lambda: self._tabs.setCurrentIndex(0))
        existing_layout.addWidget(view_in_my_prs_btn)
        existing_layout.addStretch(1)
        self._open_pr_stack.addWidget(existing_pr_widget)

        open_pr_layout.addWidget(self._open_pr_stack)
        self._tabs.addTab(open_pr_widget, "Open PR")

        # ── connect VM signals ──────────────────────────────────────────────
        vm.loading_started.connect(self._on_loading_started)
        vm.prs_updated.connect(self._on_prs_updated)
        vm.pr_detail_updated.connect(self._on_pr_detail_updated)
        vm.token_state_changed.connect(self._apply_token_state)
        vm.refresh_error.connect(self._on_refresh_error)

        self._apply_token_state()
        self._populate_open_pr_form()

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
            self._vm.refresh_prs()

    def _toggle_token_form(self):
        visible = self._token_rotate_widget.isVisible()
        self._token_rotate_widget.setVisible(not visible)

    def _save_rotated_token(self):
        token = self._token_rotate_input.text().strip()
        if token:
            self._vm.save_token(token)
            self._token_rotate_input.clear()
            self._token_rotate_widget.hide()
            self._vm.refresh_prs()

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
        self._pr_list.show()
        self._pr_error_label.hide()
        self._pr_list.clear()
        current_branch = _current_git_branch(getattr(self._vm, "_repo_path", ""))
        for pr in self._vm.prs:
            status = self._ci_badge(pr)
            unread = self._vm.unread_comment_count(pr.number)
            badge = f"🔴 {unread} new  " if unread > 0 else ""
            label = f"#{pr.number}  {pr.title}   {badge}{status}"
            if pr.head_branch == current_branch:
                label += "   ← current branch"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, pr.number)
            self._pr_list.addItem(item)
        self._check_open_pr_tab()

    def _ci_badge(self, pr: PullRequest) -> str:
        s = pr.ci_status()
        return {"running": "⏳", "failed": "❌", "passed": "✅", "unknown": "–"}.get(s, "–")

    def _on_pr_row_activated(self, item: QListWidgetItem):
        pr_number = item.data(Qt.UserRole)
        self._vm.select_pr(pr_number)

    def _on_pr_detail_updated(self):
        pr = self._vm.selected_pr
        if pr is None:
            self._my_prs_stack.setCurrentWidget(self._pr_list_widget)
            return
        self._my_prs_stack.setCurrentWidget(self._pr_detail_widget)
        self._vm.mark_pr_comments_seen(pr.number)
        self._detail_title_label.setText(f"#{pr.number}  {pr.title}\n{pr.head_branch} → {pr.base_branch}")

        try:
            self._copy_url_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._copy_url_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(pr.html_url)
        )
        try:
            self._open_url_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._open_url_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(pr.html_url))
        )

        self._checks_list.clear()
        for c in pr.checks:
            conclusion = c.conclusion or "running"
            badge = {"success": "✅", "failure": "❌"}.get(conclusion, "⏳")
            self._checks_list.addItem(f"● {c.name}   {badge} {conclusion}")

        failed_checks = [c for c in pr.checks if c.conclusion == "failure"]
        if failed_checks:
            self._rerun_btn.show()
            suite_id = failed_checks[0].check_suite_id
            try:
                self._rerun_btn.clicked.disconnect()
            except RuntimeError:
                pass
            self._rerun_btn.clicked.connect(
                lambda checked=False, sid=suite_id, p=pr: self._vm._svc.rerun_failed_checks(sid, p) if self._vm._svc else None
            )
        else:
            self._rerun_btn.hide()

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

        s = pr.ci_status()
        if s == "running":
            self._merge_status_label.setText("⏳ Checks running — not ready to merge")
        elif s == "failed":
            self._merge_status_label.setText("❌ Checks failed")
        elif s == "passed" and pr.is_ready_to_merge():
            self._merge_status_label.setText("✅ Ready to merge")
        else:
            self._merge_status_label.setText("")

    def _on_back(self):
        self._vm.deselect_pr()
        self._my_prs_stack.setCurrentWidget(self._pr_list_widget)

    # ── Open PR form ───────────────────────────────────────────────────────────

    def _populate_open_pr_form(self):
        repo_path = getattr(self._vm, "_repo_path", "") or ""
        branch = _current_git_branch(repo_path)
        self._branch_label.setText(f"Current branch: {branch}")

        # Pre-fill title from branch name
        title = branch.split("/")[-1].replace("-", " ").replace("_", " ").title() if branch else ""
        self._pr_title_edit.setText(title)

        # Pre-fill description from PR template
        template_path = Path(repo_path) / ".github" / "pull_request_template.md"
        if template_path.exists():
            self._description_edit.setPlainText(template_path.read_text())

        # Base branch suggestions
        self._base_branch_combo.clear()
        self._base_branch_combo.addItem("main")
        self._base_branch_combo.addItem("master")

        self._check_open_pr_tab()

    def _check_open_pr_tab(self):
        """Show existing-PR summary if current branch already has an open PR."""
        repo_path = getattr(self._vm, "_repo_path", "") or ""
        current_branch = _current_git_branch(repo_path)
        existing = next((p for p in self._vm.prs if p.head_branch == current_branch), None)
        if existing:
            badge = self._ci_badge(existing)
            self._existing_pr_label.setText(
                f"PR already open:\n#{existing.number}  {existing.title}  {badge}"
            )
            self._open_pr_stack.setCurrentIndex(1)
        else:
            self._open_pr_stack.setCurrentIndex(0)

    def _on_push_open_pr(self):
        title = self._pr_title_edit.text().strip()
        body = self._description_edit.toPlainText()
        base = self._base_branch_combo.currentText()
        draft = self._draft_checkbox.isChecked()
        repo_path = getattr(self._vm, "_repo_path", "") or ""
        branch = _current_git_branch(repo_path)

        self._open_pr_error_label.hide()
        self._push_open_btn.setEnabled(False)
        self._push_open_btn.setText("Pushing…")

        try:
            svc = self._vm._svc
            if svc is None:
                raise RuntimeError("GitHub service not configured")
            svc.push_branch(branch, repo_path=repo_path)
            svc.create_pull_request(title=title, body=body, base=base, draft=draft)
            self._vm.refresh_prs()
            self._tabs.setCurrentIndex(0)
        except Exception as exc:
            self._open_pr_error_label.setText(str(exc))
            self._open_pr_error_label.show()
        finally:
            self._push_open_btn.setEnabled(True)
            self._push_open_btn.setText("Push & Open PR")
