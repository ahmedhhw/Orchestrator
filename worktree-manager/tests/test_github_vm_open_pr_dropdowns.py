import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


@pytest.fixture
def vm(store):
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = MagicMock()
        v = GitHubViewModel(store=store)
    return v


# --- list_open_pr_repos ---

def test_list_open_pr_repos_returns_repo_paths_from_store(vm, store):
    from worktree_manager.models import RepoConfig
    cfg = RepoConfig(
        repo_path="/repos/alpha",
        worktree_storage="/repos/alpha/.worktrees",
        stale_days=14,
        last_editor="code",
        last_editor_mode="reuse",
        last_opened=0,
        commands=[],
    )
    store.save_repo(cfg)
    repos = vm.list_open_pr_repos()
    assert "/repos/alpha" in repos


def test_list_open_pr_repos_returns_empty_when_no_repos(vm):
    repos = vm.list_open_pr_repos()
    assert repos == []


def test_list_open_pr_repos_returns_multiple_repos(vm, store):
    from worktree_manager.models import RepoConfig
    for path in ["/repos/alpha", "/repos/beta"]:
        store.save_repo(RepoConfig(
            repo_path=path,
            worktree_storage=path + "/.worktrees",
            stale_days=14, last_editor="code",
            last_editor_mode="reuse", last_opened=0, commands=[],
        ))
    repos = vm.list_open_pr_repos()
    assert set(repos) == {"/repos/alpha", "/repos/beta"}


# --- list_branches_for_repo ---

def test_list_branches_for_repo_calls_git_service(vm):
    mock_git = MagicMock()
    mock_git.list_local_branches.return_value = ["main", "feature/foo"]
    with patch("worktree_manager.github_vm.GitService", return_value=mock_git):
        branches = vm.list_branches_for_repo("/repos/alpha")
    assert branches == ["main", "feature/foo"]


def test_list_branches_for_repo_returns_empty_on_error(vm):
    mock_git = MagicMock()
    mock_git.list_local_branches.side_effect = Exception("not a git repo")
    with patch("worktree_manager.github_vm.GitService", return_value=mock_git):
        branches = vm.list_branches_for_repo("/not/a/repo")
    assert branches == []
