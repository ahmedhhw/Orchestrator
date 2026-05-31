import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck


def _make_pr(number=1, mergeable=None, mergeable_state=""):
    return PullRequest(
        number=number, title="My PR", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=mergeable,
        mergeable_state=mergeable_state,
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
    from worktree_manager.github_vm import GitHubViewModel
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        svc = MagicMock()
        svc.get_authenticated_user.return_value = "me"
        svc.discover_open_prs.return_value = []
        MockSvc.return_value = svc
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    v._svc.get_pr_detail.reset_mock()
    return v


def test_select_pr_updates_selected_pr_with_detail(vm, qtbot):
    listed = _make_pr(42, mergeable=None)
    detailed = _make_pr(42, mergeable=True)
    vm.prs = [listed]
    vm._svc.get_pr_detail.return_value = detailed

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(listed)

    assert vm.selected_pr.mergeable is True


def test_fetch_carries_forward_mergeable_when_null_returned(vm, qtbot):
    """If a per-PR fetch returns mergeable=None, the last known value is preserved."""
    vm.prs = [_make_pr(42, mergeable=True, mergeable_state="clean")]
    vm._known_prs = [("myorg", "myrepo", 42)]

    fresh = _make_pr(42, mergeable=None, mergeable_state="unknown")
    vm._svc.get_pr_detail.return_value = fresh

    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.quick_fetch()

    assert vm.prs[0].mergeable is True
    assert vm.prs[0].mergeable_state == "clean"
