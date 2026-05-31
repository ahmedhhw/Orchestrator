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


def test_list_remote_branches_calls_git_service(vm):
    mock_git = MagicMock()
    mock_git.list_remote_branches.return_value = ["main", "develop"]
    with patch("worktree_manager.github_vm.GitService", return_value=mock_git):
        branches = vm.list_remote_branches_for_repo("/repos/myrepo")
    mock_git.list_remote_branches.assert_called_once_with("/repos/myrepo")
    assert branches == ["main", "develop"]


def test_list_remote_branches_returns_empty_on_error(vm):
    mock_git = MagicMock()
    mock_git.list_remote_branches.side_effect = Exception("not a git repo")
    with patch("worktree_manager.github_vm.GitService", return_value=mock_git):
        branches = vm.list_remote_branches_for_repo("/not/a/repo")
    assert branches == []
