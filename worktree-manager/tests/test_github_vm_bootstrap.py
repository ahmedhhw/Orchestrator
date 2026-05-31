import pytest
from unittest.mock import MagicMock, patch, call
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
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        svc = MagicMock()
        svc.get_authenticated_user.return_value = "me"
        svc.discover_open_pr_repos.return_value = set()
        svc.list_prs_for_repo.return_value = []
        svc.fetch_check_runs.return_value = []
        svc.fetch_mergeable.return_value = None
        MockSvc.return_value = svc
        v = GitHubViewModel(store=store)
        # Stop the poll timer immediately so it never fires
        v._timer.stop()
    # Drain the singleShot so the initial auto-refresh completes
    with qtbot.waitSignal(v.prs_updated, timeout=2000):
        pass
    # Reset all mock call counts so tests start clean
    v._svc.discover_open_pr_repos.reset_mock()
    v._svc.list_prs_for_repo.reset_mock()
    v._svc.fetch_check_runs.reset_mock()
    v._svc.fetch_mergeable.reset_mock()
    v._svc.get_authenticated_user.reset_mock()
    # Reset VM state so each test controls bootstrap from scratch
    v._known_repos = set()
    v._login = ""
    return v


# ── bootstrap ────────────────────────────────────────────────────────────────

def test_refresh_prs_calls_discover_on_first_run(vm, qtbot):
    vm._svc.discover_open_pr_repos.return_value = {("myorg", "myrepo")}
    vm._svc.list_prs_for_repo.return_value = []
    vm._login = "me"
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    vm._svc.discover_open_pr_repos.assert_called_once_with("me")


def test_refresh_prs_skips_discover_on_subsequent_runs(vm, qtbot):
    vm._known_repos = {("myorg", "myrepo")}
    vm._login = "me"
    vm._svc.list_prs_for_repo.return_value = []
    vm._svc.fetch_check_runs.return_value = []
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    vm._svc.discover_open_pr_repos.assert_not_called()


def test_refresh_prs_populates_known_repos_after_bootstrap(vm, qtbot):
    vm._svc.discover_open_pr_repos.return_value = {("myorg", "api"), ("myorg", "frontend")}
    vm._svc.list_prs_for_repo.return_value = []
    vm._login = "me"
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    assert ("myorg", "api") in vm._known_repos
    assert ("myorg", "frontend") in vm._known_repos


def test_refresh_prs_merges_prs_from_all_known_repos(vm, qtbot):
    vm._known_repos = {("myorg", "api"), ("myorg", "frontend")}
    vm._login = "me"
    pr1 = _make_pr(1, "myorg", "api")
    pr2 = _make_pr(2, "myorg", "frontend")
    vm._svc.list_prs_for_repo.side_effect = lambda o, r, l: [pr1] if r == "api" else [pr2]
    vm._svc.fetch_check_runs.return_value = []
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    assert len(vm.prs) == 2
    assert {p.number for p in vm.prs} == {1, 2}


def test_refresh_prs_attaches_check_runs_to_each_pr(vm, qtbot):
    vm._known_repos = {("myorg", "myrepo")}
    vm._login = "me"
    pr = _make_pr(1, sha="deadbeef")
    vm._svc.list_prs_for_repo.return_value = [pr]
    checks = [CICheck("build", "completed", "success")]
    vm._svc.fetch_check_runs.return_value = checks
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    assert vm.prs[0].checks == checks
    vm._svc.fetch_check_runs.assert_called_once_with("myorg", "myrepo", "deadbeef")


def test_refresh_prs_auto_adds_new_repo_discovered_via_pr(vm, qtbot):
    """A PR in a repo not yet in _known_repos gets its repo added automatically."""
    vm._known_repos = {("myorg", "api")}
    vm._login = "me"
    vm._svc.list_prs_for_repo.side_effect = lambda o, r, l: [_make_pr(1, "myorg", "api")] if r == "api" else []
    vm._svc.fetch_check_runs.return_value = []
    vm._add_repo_if_new("myorg", "new-repo")
    assert ("myorg", "new-repo") in vm._known_repos


# ── fetch_status_changed signal ──────────────────────────────────────────────

def test_fetch_status_changed_emits_scanning_during_bootstrap(vm, qtbot):
    vm._svc.discover_open_pr_repos.return_value = set()
    vm._login = "me"
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    assert any("Scanning" in s for s in statuses)


def test_fetch_status_changed_emits_tracking_when_idle(vm, qtbot):
    vm._known_repos = {("myorg", "myrepo")}
    vm._login = "me"
    vm._svc.list_prs_for_repo.return_value = []
    vm._svc.fetch_check_runs.return_value = []
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    assert any("Tracking" in s for s in statuses)


def test_fetch_status_changed_includes_repo_names_in_tracking(vm, qtbot):
    from PySide6.QtWidgets import QApplication
    vm._known_repos = {("myorg", "api"), ("myorg", "frontend")}
    vm._login = "me"
    vm._svc.list_prs_for_repo.return_value = []
    vm._svc.fetch_check_runs.return_value = []
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    QApplication.processEvents()
    idle = next(s for s in statuses if "Tracking" in s)
    assert "myorg/api" in idle or "myorg/frontend" in idle


def test_fetch_status_changed_emits_no_repos_when_none_tracked(vm, qtbot):
    vm._known_repos = set()
    vm._login = "me"
    vm._svc.discover_open_pr_repos.return_value = set()
    statuses = []
    vm.fetch_status_changed.connect(statuses.append)
    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()
    assert any("Tracking" in s or "No repos" in s for s in statuses)


# ── fetch_mergeable during refresh ───────────────────────────────────────────

def test_refresh_prs_populates_mergeable_for_each_pr(vm, qtbot):
    """After refresh_prs, vm.prs[0].mergeable is populated — no 'View' needed."""
    vm._known_repos = {("myorg", "myrepo")}
    vm._login = "me"
    pr = _make_pr(1, sha="deadbeef")
    pr.mergeable = None  # simulate list-endpoint value
    vm._svc.list_prs_for_repo.return_value = [pr]
    vm._svc.fetch_check_runs.return_value = []
    vm._svc.fetch_mergeable.return_value = True

    with qtbot.waitSignal(vm.prs_updated, timeout=2000):
        vm.refresh_prs()

    assert vm.prs[0].mergeable is True
    vm._svc.fetch_mergeable.assert_called_once_with("myorg", "myrepo", 1)


# ── rescan_repos ─────────────────────────────────────────────────────────────

def test_rescan_repos_clears_known_repos(vm, qtbot):
    vm._known_repos = {("myorg", "api")}
    vm._login = "me"
    vm.rescan_repos()
    assert vm._known_repos == set()


def test_rescan_repos_clears_login_so_next_refresh_re_bootstraps(vm, qtbot):
    vm._known_repos = {("myorg", "api")}
    vm._login = "me"
    with patch.object(vm, "refresh_prs"):
        vm.rescan_repos()
    assert vm._login == ""


def test_rescan_repos_triggers_refresh(vm, qtbot):
    vm._known_repos = {("myorg", "api")}
    vm._login = "me"
    with patch.object(vm, "refresh_prs") as mock_refresh:
        vm.rescan_repos()
    mock_refresh.assert_called_once()
