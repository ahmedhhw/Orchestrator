import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck


def _make_pr(number=1, mergeable=True):
    return PullRequest(
        number=number, title="My PR", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=mergeable,
        head_sha="abc123",
        checks=[CICheck("build", "completed", "failure")],
    )


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


@pytest.fixture
def vm(store, qtbot):
    from PySide6.QtWidgets import QApplication
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        svc = MagicMock()
        svc.get_authenticated_user.return_value = "me"
        svc.discover_open_prs.return_value = []
        MockSvc.return_value = svc
        from worktree_manager.github_vm import GitHubViewModel
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    QApplication.processEvents()
    v._svc.get_pr_detail.reset_mock()
    return v


def test_select_pr_reflects_mergeable_from_detail(vm, qtbot):
    pr = _make_pr(42, mergeable=True)
    vm.prs = [pr]
    vm._svc.get_pr_detail.return_value = pr
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(pr)
    assert vm.selected_pr.mergeable is True
    assert vm._svc.get_pr_detail.call_count == 1


def test_select_pr_with_null_mergeable_shows_none(vm, qtbot):
    """mergeable=None from detail is shown as-is; no retry fires."""
    pr_null = _make_pr(42, mergeable=None)
    listed = _make_pr(42, mergeable=None)
    vm.prs = [listed]
    vm._svc.get_pr_detail.return_value = pr_null
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(listed)
    assert vm.selected_pr.mergeable is None
    # No retry: get_pr_detail should only be called once
    qtbot.wait(500)
    assert vm._svc.get_pr_detail.call_count == 1
