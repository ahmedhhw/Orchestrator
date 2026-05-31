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
        svc.discover_open_pr_repos.return_value = set()
        svc.list_prs_for_repo.return_value = []
        svc.fetch_check_runs.return_value = []
        MockSvc.return_value = svc
        from worktree_manager.github_vm import GitHubViewModel
        v = GitHubViewModel(store=store)
        v._timer.stop()
    QApplication.processEvents()
    v._svc.get_pr_detail.reset_mock()
    return v


def test_select_pr_schedules_retry_when_mergeable_is_none(vm, qtbot):
    """When get_pr_detail returns mergeable=None, a retry fires after 2s."""
    pr_null = _make_pr(42, mergeable=None)
    pr_resolved = _make_pr(42, mergeable=True)
    vm.prs = [_make_pr(42, mergeable=None)]
    vm._svc.get_pr_detail.side_effect = [pr_null, pr_resolved]

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=3000):
        vm.select_pr(42)

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=3000):
        pass

    assert vm.selected_pr.mergeable is True
    assert vm._svc.get_pr_detail.call_count == 2


def test_select_pr_no_retry_when_mergeable_is_known(vm, qtbot):
    """No retry is scheduled when mergeable is already True or False."""
    pr = _make_pr(42, mergeable=True)
    vm.prs = [pr]
    vm._svc.get_pr_detail.return_value = pr

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)

    # Wait long enough that a retry would have fired if scheduled
    qtbot.wait(2500)
    assert vm._svc.get_pr_detail.call_count == 1


def test_refetch_mergeable_noops_if_pr_changed(vm, qtbot):
    """If the user navigates away before the retry fires, it does nothing."""
    pr_null = _make_pr(42, mergeable=None)
    pr_other = _make_pr(99, mergeable=True)
    vm.prs = [pr_null]
    vm._svc.get_pr_detail.return_value = pr_null

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)

    # Navigate to a different PR before the 2s timer fires
    vm.selected_pr = pr_other

    # Wait for the timer; it must not call get_pr_detail again for PR 42
    qtbot.wait(2500)
    assert vm._svc.get_pr_detail.call_count == 1
