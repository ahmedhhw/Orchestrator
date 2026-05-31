import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QLabel
from worktree_manager.github_models import PullRequest, CICheck, Review
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, head="feat", base="main", checks=None, reviews=None, mergeable=True):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch=head, base_branch=base,
        state="open", draft=False, mergeable=mergeable,
        checks=checks or [], reviews=reviews or [],
    )


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
    v._timer.stop()
    return v


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    return p


def _row_label_text(panel, row: int) -> str:
    item = panel._pr_list.item(row)
    widget = panel._pr_list.itemWidget(item)
    label = widget.findChild(QLabel)
    return label.text() if label else ""


def _row_view_btn(panel, row: int) -> QPushButton:
    item = panel._pr_list.item(row)
    widget = panel._pr_list.itemWidget(item)
    return widget.findChild(QPushButton)


# ── two-line row format ───────────────────────────────────────────────────────

def test_pr_row_label_contains_number_and_title(vm, panel, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    text = _row_label_text(panel, 0)
    assert "#42" in text
    assert "PR 42" in text


def test_pr_row_label_contains_head_to_base(vm, panel, qtbot):
    vm.prs = [_make_pr(1, head="feature/x", base="main")]
    vm.prs_updated.emit()
    text = _row_label_text(panel, 0)
    assert "feature/x → main" in text


def test_pr_row_label_has_newline_separating_lines(vm, panel, qtbot):
    vm.prs = [_make_pr(1)]
    vm.prs_updated.emit()
    text = _row_label_text(panel, 0)
    assert "\n" in text


# ── view button ───────────────────────────────────────────────────────────────

def test_pr_row_has_view_button(vm, panel, qtbot):
    vm.prs = [_make_pr(1)]
    vm.prs_updated.emit()
    btn = _row_view_btn(panel, 0)
    assert btn is not None


def test_view_button_opens_detail(vm, panel, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    with patch.object(vm, "select_pr") as mock_select:
        _row_view_btn(panel, 0).click()
    mock_select.assert_called_once_with(42)


def test_multiple_rows_view_buttons_call_correct_pr(vm, panel, qtbot):
    vm.prs = [_make_pr(10), _make_pr(20)]
    vm.prs_updated.emit()
    with patch.object(vm, "select_pr") as mock_select:
        _row_view_btn(panel, 1).click()
    mock_select.assert_called_once_with(20)


# ── descriptive status badge ─────────────────────────────────────────────────

def test_badge_shows_checks_running(vm, panel, qtbot):
    vm.prs = [_make_pr(1, checks=[CICheck("build", "in_progress", None)])]
    vm.prs_updated.emit()
    assert "checks running" in _row_label_text(panel, 0)


def test_badge_shows_checks_failed(vm, panel, qtbot):
    vm.prs = [_make_pr(1, checks=[CICheck("build", "completed", "failure")])]
    vm.prs_updated.emit()
    assert "checks failed" in _row_label_text(panel, 0)


def test_badge_shows_ready_to_merge(vm, panel, qtbot):
    vm.prs = [_make_pr(
        1,
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )]
    vm.prs_updated.emit()
    assert "ready to merge" in _row_label_text(panel, 0)


def test_badge_shows_checks_passed_when_not_mergeable(vm, panel, qtbot):
    vm.prs = [_make_pr(1, checks=[CICheck("build", "completed", "success")], mergeable=False)]
    vm.prs_updated.emit()
    assert "checks passed" in _row_label_text(panel, 0)


def test_badge_shows_no_checks(vm, panel, qtbot):
    vm.prs = [_make_pr(1, checks=[])]
    vm.prs_updated.emit()
    assert "no checks" in _row_label_text(panel, 0)


# ── current branch label removed ─────────────────────────────────────────────

def test_current_branch_label_absent(vm, panel, qtbot):
    vm.prs = [_make_pr(1, head="main"), _make_pr(2, head="feat")]
    vm.prs_updated.emit()
    for i in range(panel._pr_list.count()):
        assert "current branch" not in _row_label_text(panel, i)


# ── footer bar ───────────────────────────────────────────────────────────────

def test_footer_label_exists(panel):
    assert hasattr(panel, "_fetch_status_label")


def test_rescan_button_exists(panel):
    assert hasattr(panel, "_rescan_btn")


def test_fetch_status_signal_updates_footer_label(vm, panel, qtbot):
    vm.fetch_status_changed.emit("Tracking: myorg/api")
    assert "myorg/api" in panel._fetch_status_label.text()


def test_rescan_button_calls_vm_rescan(vm, panel, qtbot):
    with patch.object(vm, "rescan_repos") as mock_rescan:
        panel._rescan_btn.click()
    mock_rescan.assert_called_once()


# ── right-click context menu ──────────────────────────────────────────────────

def test_context_menu_view_action_calls_select_pr(vm, panel, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    with patch.object(vm, "select_pr") as mock_select, \
         patch("worktree_manager.ui.github_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        view_action = MagicMock()
        view_action.text.return_value = "↗ View details"
        mock_menu.exec.return_value = view_action
        mock_menu.addAction.return_value = view_action
        panel._show_pr_context_menu(42, panel._pr_list.item(0))
    mock_select.assert_called_once_with(42)


def test_context_menu_merge_action_absent_when_not_ready(vm, panel, qtbot):
    pr = _make_pr(1, checks=[CICheck("build", "completed", "failure")], mergeable=False)
    vm.prs = [pr]
    vm.prs_updated.emit()
    actions_added = []
    with patch("worktree_manager.ui.github_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        mock_menu.exec.return_value = None
        mock_menu.addAction.side_effect = lambda text: actions_added.append(text)
        panel._show_pr_context_menu(1, panel._pr_list.item(0))
    assert not any("Merge" in a for a in actions_added)


def test_context_menu_merge_action_present_when_ready(vm, panel, qtbot):
    pr = _make_pr(
        1,
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    vm.prs = [pr]
    vm.prs_updated.emit()
    actions_added = []
    with patch("worktree_manager.ui.github_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        mock_menu.exec.return_value = None
        mock_menu.addAction.side_effect = lambda text: actions_added.append(text)
        panel._show_pr_context_menu(1, panel._pr_list.item(0))
    assert any("Merge" in a for a in actions_added)


def test_context_menu_merge_action_calls_vm_merge(vm, panel, qtbot):
    pr = _make_pr(
        42,
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    vm.prs = [pr]
    vm.prs_updated.emit()
    with patch.object(vm, "merge_pr") as mock_merge, \
         patch("worktree_manager.ui.github_panel.QMenu") as MockMenu:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        merge_action = MagicMock()
        merge_action.text.return_value = "✓ Merge (squash)"
        mock_menu.exec.return_value = merge_action
        mock_menu.addAction.return_value = merge_action
        panel._show_pr_context_menu(42, panel._pr_list.item(0))
    mock_merge.assert_called_once_with(42, squash=True)


def test_context_menu_copy_url_writes_clipboard(vm, panel, qtbot):
    vm.prs = [_make_pr(42)]
    vm.prs_updated.emit()
    with patch("worktree_manager.ui.github_panel.QMenu") as MockMenu, \
         patch("worktree_manager.ui.github_panel.QApplication") as MockApp:
        mock_menu = MagicMock()
        MockMenu.return_value = mock_menu
        copy_action = MagicMock()
        copy_action.text.return_value = "⧉ Copy URL"
        mock_menu.exec.return_value = copy_action
        mock_menu.addAction.return_value = copy_action
        panel._show_pr_context_menu(42, panel._pr_list.item(0))
    MockApp.clipboard.return_value.setText.assert_called()
