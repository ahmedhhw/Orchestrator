import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QClipboard
from worktree_manager.github_vm import GitHubViewModel, TokenState
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment
from worktree_manager.ui.github_panel import GitHubPanel


def _make_pr(number=1, head="feat", base="main", checks=None, reviews=None, comments=None, html_url=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="", html_url=html_url or f"https://github.com/o/r/pull/{number}",
        head_branch=head, base_branch=base, state="open", draft=False, mergeable=True,
        checks=checks or [], reviews=reviews or [], comments=comments or [],
    )


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    with patch("worktree_manager.github_vm.GitHubService"), \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        v = GitHubViewModel(store=store, repo_path="/tmp/repo")
    return v


@pytest.fixture
def configured_vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc, \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        MockSvc.from_remote_url.return_value = MagicMock()
        v = GitHubViewModel(store=store, repo_path="/tmp/repo")
    return v


@pytest.fixture
def panel(vm, qtbot):
    p = GitHubPanel(vm=vm)
    qtbot.addWidget(p)
    p.show()
    return p


@pytest.fixture
def configured_panel(configured_vm, qtbot):
    p = GitHubPanel(vm=configured_vm)
    qtbot.addWidget(p)
    p.show()
    return p


def _show_detail(panel, vm, pr):
    vm.selected_pr = pr
    vm.pr_detail_updated.emit()


def test_copy_url_button_exists_on_detail_view(configured_panel, configured_vm, qtbot):
    pr = _make_pr(42, html_url="https://github.com/o/r/pull/42")
    _show_detail(configured_panel, configured_vm, pr)
    assert hasattr(configured_panel, "_copy_url_btn")
    assert configured_panel._copy_url_btn is not None


def test_open_url_button_exists_on_detail_view(configured_panel, configured_vm, qtbot):
    pr = _make_pr(42, html_url="https://github.com/o/r/pull/42")
    _show_detail(configured_panel, configured_vm, pr)
    assert hasattr(configured_panel, "_open_url_btn")
    assert configured_panel._open_url_btn is not None


def test_copy_url_writes_to_clipboard(configured_panel, configured_vm, qtbot):
    pr = _make_pr(42, html_url="https://github.com/o/r/pull/42")
    _show_detail(configured_panel, configured_vm, pr)
    configured_panel._copy_url_btn.click()
    clipboard = QApplication.clipboard()
    assert clipboard.text() == "https://github.com/o/r/pull/42"


def test_open_url_calls_desktop_services(configured_panel, configured_vm, qtbot):
    pr = _make_pr(42, html_url="https://github.com/o/r/pull/42")
    _show_detail(configured_panel, configured_vm, pr)
    with patch("worktree_manager.ui.github_panel.QDesktopServices.openUrl") as mock_open:
        configured_panel._open_url_btn.click()
    mock_open.assert_called_once()
    called_url = mock_open.call_args[0][0]
    assert "pull/42" in called_url.toString()


# Phase 1.2 — Re-run CI button

def test_rerun_button_hidden_when_no_failures(configured_panel, configured_vm, qtbot):
    pr = _make_pr(42, checks=[CICheck("build", "completed", "success", "suite-1")])
    _show_detail(configured_panel, configured_vm, pr)
    assert not configured_panel._rerun_btn.isVisible()


def test_rerun_button_visible_when_check_failed(configured_panel, configured_vm, qtbot):
    pr = _make_pr(42, checks=[CICheck("build", "completed", "failure", "suite-1")])
    _show_detail(configured_panel, configured_vm, pr)
    assert configured_panel._rerun_btn.isVisible()


def test_rerun_button_calls_service(configured_panel, configured_vm, qtbot):
    failed_check = CICheck("build", "completed", "failure", "suite-99")
    pr = _make_pr(42, checks=[failed_check])
    _show_detail(configured_panel, configured_vm, pr)
    configured_vm._svc = MagicMock()
    configured_panel._rerun_btn.click()
    configured_vm._svc.rerun_failed_checks.assert_called_once_with("suite-99", pr)
