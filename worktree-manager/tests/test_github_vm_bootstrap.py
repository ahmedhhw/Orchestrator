import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck
from worktree_manager.github_vm import GitHubViewModel, TokenState


def _make_pr(number=1, owner="myorg", repo="myrepo", sha="abc"):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        head_sha=sha,
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
    import time
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        svc = MagicMock()
        svc.get_authenticated_user.return_value = "me"
        svc.discover_open_prs.return_value = []
        MockSvc.return_value = svc
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    deadline = time.monotonic() + 3.0
    while not v._initial_load_done and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.02)
    deadline2 = time.monotonic() + 1.0
    while v._total_fetch_running and time.monotonic() < deadline2:
        time.sleep(0.01)
    QApplication.processEvents()
    v._svc.discover_open_prs.reset_mock()
    v._svc.get_pr_detail.reset_mock()
    v._login = ""
    v._known_prs = []
    v.prs = []
    v._pr_state = {}
    return v


# ── bootstrap ────────────────────────────────────────────────────────────────

def test_total_fetch_calls_discover(vm, qtbot):
    vm._svc.discover_open_prs.return_value = [("myorg", "myrepo", 1)]
    vm._svc.get_pr_detail.return_value = _make_pr(1)
    vm._login = "me"
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.total_fetch()
    vm._svc.discover_open_prs.assert_called_once_with("me")


def test_quick_fetch_skips_discover(vm, qtbot):
    vm._known_prs = [("myorg", "myrepo", 1)]
    vm._login = "me"
    vm._svc.get_pr_detail.return_value = _make_pr(1)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.quick_fetch()
    vm._svc.discover_open_prs.assert_not_called()


def test_total_fetch_populates_known_prs(vm, qtbot):
    vm._svc.discover_open_prs.return_value = [("myorg", "api", 1), ("myorg", "frontend", 2)]
    vm._svc.get_pr_detail.side_effect = lambda n, pr=None: _make_pr(n)
    vm._login = "me"
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.total_fetch()
    numbers = [n for _, _, n in vm._known_prs]
    assert 1 in numbers
    assert 2 in numbers


def test_total_fetch_fetches_each_discovered_pr(vm, qtbot):
    vm._svc.discover_open_prs.return_value = [("myorg", "api", 1), ("myorg", "frontend", 2)]
    vm._svc.get_pr_detail.side_effect = lambda n, pr=None: _make_pr(n)
    vm._login = "me"
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.total_fetch()
    assert len(vm.prs) == 2
    assert {p.number for p in vm.prs} == {1, 2}


def test_fetch_mergeable_comes_from_per_pr_endpoint(vm, qtbot):
    pr = _make_pr(1, sha="deadbeef")
    pr.mergeable = True
    vm._known_prs = [("myorg", "myrepo", 1)]
    vm._login = "me"
    vm._svc.get_pr_detail.return_value = pr
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.quick_fetch()
    assert vm.prs[0].mergeable is True


# ── fetch_status_changed signal ──────────────────────────────────────────────

def test_fetch_status_changed_emits_scanning_on_total_fetch(vm, qtbot):
    vm._svc.discover_open_prs.return_value = []
    vm._login = "me"
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.total_fetch()
    assert any("Scanning" in s for s in statuses)


def test_fetch_status_changed_emits_tracking_when_done(vm, qtbot):
    vm._known_prs = [("myorg", "myrepo", 1)]
    vm._login = "me"
    vm._svc.get_pr_detail.return_value = _make_pr(1)
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.quick_fetch()
    assert any("Tracking" in s for s in statuses)


def test_fetch_status_includes_repo_name_in_tracking(vm, qtbot):
    vm._known_prs = [("myorg", "api", 1)]
    vm._login = "me"
    vm._svc.get_pr_detail.return_value = _make_pr(1)
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.quick_fetch()
    idle = next(s for s in statuses if "Tracking" in s)
    assert "myorg/api" in idle


def test_fetch_status_no_prs_message(vm, qtbot):
    vm._login = "me"
    vm._svc.discover_open_prs.return_value = []
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.total_fetch()
    assert any("no open PRs" in s for s in statuses)


# ── rescan_repos ─────────────────────────────────────────────────────────────

def test_rescan_repos_clears_known_prs(vm, qtbot):
    vm._known_prs = [("myorg", "api", 1)]
    vm._login = "me"
    with patch.object(vm, "total_fetch"):
        vm.rescan_repos()
    assert vm._known_prs == []


def test_rescan_repos_clears_login(vm, qtbot):
    vm._known_prs = [("myorg", "api", 1)]
    vm._login = "me"
    with patch.object(vm, "total_fetch"):
        vm.rescan_repos()
    assert vm._login == ""


def test_rescan_repos_triggers_total_fetch(vm, qtbot):
    vm._known_prs = [("myorg", "api", 1)]
    vm._login = "me"
    with patch.object(vm, "total_fetch") as mock_fetch:
        vm.rescan_repos()
    mock_fetch.assert_called_once()
