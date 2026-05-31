import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment
from worktree_manager.github_vm import GitHubViewModel, TokenState


def _make_pr(number=1, head="feat", base="main", checks=None, reviews=None, comments=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="", html_url=f"http://x/{number}",
        head_branch=head, base_branch=base, state="open", draft=False, mergeable=True,
        checks=checks or [], reviews=reviews or [], comments=comments or [],
    )


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


# ── token state ──────────────────────────────────────────────────────────────


def test_vm_enters_configured_state_with_token_only(tmp_path):
    store = MagicMock()
    store.get_github_token.return_value = "ghp_test"
    store.get_github_owner.return_value = ""
    store.get_github_repo.return_value = ""
    store.get_github_poll_interval.return_value = 30

    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store, repo_path="")
    assert vm.token_state == TokenState.CONFIGURED
    vm.deleteLater()


def test_initial_token_state_configured_when_token_exists(store, qtbot):
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
    assert vm.token_state == TokenState.CONFIGURED
    vm.deleteLater()


def test_initial_token_state_missing_when_no_token(tmp_path, qtbot):
    from worktree_manager.config_store import ConfigStore
    empty_store = ConfigStore(path=tmp_path / "c.json")
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=empty_store, repo_path="/tmp/repo")
    assert vm.token_state == TokenState.MISSING
    vm.deleteLater()


def test_save_token_updates_state_to_configured(tmp_path, qtbot):
    from worktree_manager.config_store import ConfigStore
    empty_store = ConfigStore(path=tmp_path / "c.json")
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=empty_store, repo_path="/tmp/repo")
        vm.save_token("ghp_new")
    assert vm.token_state == TokenState.CONFIGURED
    assert empty_store.get_github_token() == "ghp_new"
    vm.deleteLater()


# ── PR list ───────────────────────────────────────────────────────────────────


def test_refresh_prs_updates_pr_list(store, qtbot):
    prs = [_make_pr(1), _make_pr(2)]
    svc = MagicMock()
    svc.list_my_open_prs.return_value = prs
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc, \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        MockSvc.from_remote_url.return_value = svc
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
    with qtbot.waitSignal(vm.prs_updated, timeout=1000):
        vm.refresh_prs()
    assert len(vm.prs) == 2
    assert vm.prs[0].number == 1
    vm.deleteLater()


def test_refresh_prs_on_401_sets_expired_state(store, qtbot):
    svc = MagicMock()
    svc.list_my_open_prs.side_effect = PermissionError("401")
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc, \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        MockSvc.from_remote_url.return_value = svc
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
    with qtbot.waitSignal(vm.token_state_changed, timeout=1000):
        vm.refresh_prs()
    assert vm.token_state == TokenState.EXPIRED
    vm.deleteLater()


# ── PR detail ─────────────────────────────────────────────────────────────────


def test_select_pr_fetches_detail(store, qtbot):
    pr = _make_pr(42, checks=[CICheck("build", "completed", "success")])
    svc = MagicMock()
    svc.get_pr_detail.return_value = pr
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc, \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        MockSvc.from_remote_url.return_value = svc
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(42)
    assert vm.selected_pr is not None
    assert vm.selected_pr.number == 42
    vm.deleteLater()


def test_deselect_pr_clears_selection(store, qtbot):
    svc = MagicMock()
    svc.get_pr_detail.return_value = _make_pr(1)
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc, \
         patch("worktree_manager.github_vm.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/o/r.git")
        MockSvc.from_remote_url.return_value = svc
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
        vm.select_pr(1)
        vm.deselect_pr()
    assert vm.selected_pr is None
    vm.deleteLater()


# ── polling pause/resume ───────────────────────────────────────────────────────


def test_polling_starts_active(store, qtbot):
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
    assert vm.polling_active is True
    vm.deleteLater()


def test_pause_polling_stops_timer(store, qtbot):
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
        vm.pause_polling()
    assert vm.polling_active is False
    vm.deleteLater()


def test_resume_polling_restarts_timer(store, qtbot):
    with patch("worktree_manager.github_vm.GitHubService"):
        vm = GitHubViewModel(store=store, repo_path="/tmp/repo")
        vm.pause_polling()
        vm.resume_polling()
    assert vm.polling_active is True
    vm.deleteLater()
