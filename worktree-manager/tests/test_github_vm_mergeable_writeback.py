import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck


def _make_pr(number=1, mergeable=None):
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
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        svc = MagicMock()
        svc.get_authenticated_user.return_value = "me"
        svc.discover_open_pr_repos.return_value = set()
        svc.list_prs_for_repo.return_value = []
        svc.fetch_check_runs.return_value = []
        svc.fetch_mergeable.return_value = None
        MockSvc.return_value = svc
        from worktree_manager.github_vm import GitHubViewModel
        v = GitHubViewModel(store=store)
        v._timer.stop()
    with qtbot.waitSignal(v.prs_updated, timeout=2000):
        pass
    v._svc.get_pr_detail.reset_mock()
    return v


def test_select_pr_writes_mergeable_back_to_prs(vm, qtbot):
    """After select_pr, the list PR in vm.prs has mergeable updated from the detail fetch."""
    listed = _make_pr(42, mergeable=None)
    detailed = _make_pr(42, mergeable=True)
    vm.prs = [listed]
    vm._svc.get_pr_detail.return_value = detailed

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)

    assert vm.prs[0].mergeable is True


def test_select_pr_writeback_does_not_affect_other_prs(vm, qtbot):
    """Writeback only updates the selected PR, not other PRs in the list."""
    pr42 = _make_pr(42, mergeable=None)
    pr99 = _make_pr(99, mergeable=None)
    detailed42 = _make_pr(42, mergeable=True)
    vm.prs = [pr42, pr99]
    vm._svc.get_pr_detail.return_value = detailed42

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)

    assert vm.prs[1].mergeable is None


def test_refresh_prs_preserves_known_mergeable_when_fetch_returns_none(vm, qtbot):
    """If fetch_mergeable returns None (GitHub still computing), carry over the last known value."""
    vm.prs = [_make_pr(42, mergeable=True)]
    vm._known_repos = {("myorg", "myrepo")}
    fresh_pr = _make_pr(42, mergeable=None)
    vm._svc.list_prs_for_repo.return_value = [fresh_pr]
    vm._svc.fetch_check_runs.return_value = []
    vm._svc.fetch_mergeable.return_value = None  # GitHub still computing

    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()

    assert vm.prs[0].mergeable is True


def test_refetch_writes_mergeable_back_to_prs(vm, qtbot):
    """After the 2s retry resolves, vm.prs is also updated."""
    listed = _make_pr(42, mergeable=None)
    detail_null = _make_pr(42, mergeable=None)
    detail_resolved = _make_pr(42, mergeable=True)
    vm.prs = [listed]
    vm._svc.get_pr_detail.side_effect = [detail_null, detail_resolved]

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)

    # Wait for the 2s retry
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=3000):
        pass

    assert vm.prs[0].mergeable is True
