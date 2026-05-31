import pytest
from unittest.mock import MagicMock, patch, call
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment
from worktree_manager.github_vm import GitHubViewModel


def _make_pr(number=1, sha="abc"):
    return PullRequest(
        number=number, title="My PR", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        head_sha=sha,
        checks=[CICheck("build", "completed", "success")],
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
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    QApplication.processEvents()
    v._svc.get_pr_detail.reset_mock()
    return v


def test_select_pr_uses_cached_pr_from_list(vm, qtbot):
    pr = _make_pr(42)
    vm.prs = [pr]
    vm._svc.get_pr_detail.return_value = pr
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)
    call_args = vm._svc.get_pr_detail.call_args
    assert call_args[1]["pr"] is pr or call_args[0][1] is pr


def test_select_pr_does_not_refetch_checks(vm, qtbot):
    pr = _make_pr(42)
    vm.prs = [pr]
    vm._svc.get_pr_detail.return_value = pr
    vm.select_pr(42)
    vm._svc.fetch_check_runs.assert_not_called()


def test_select_pr_detail_preserves_checks_from_list(vm, qtbot):
    checks = [CICheck("build", "completed", "success")]
    pr = _make_pr(42)
    pr.checks = checks
    vm.prs = [pr]
    supplemented = _make_pr(42)
    supplemented.checks = checks
    supplemented.reviews = [Review("alice", "APPROVED")]
    vm._svc.get_pr_detail.return_value = supplemented
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)
    assert vm.selected_pr.checks == checks
