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


def test_delegates_to_git_service_infer_parent_branch(vm):
    mock_git = MagicMock()
    mock_git.infer_parent_branch.return_value = "feature/parent"
    with patch("worktree_manager.github_vm.GitService", return_value=mock_git):
        result = vm.get_parent_branch_for_repo(
            "/repos/myrepo",
            branch="feature/child",
            remote_branches=["main", "feature/parent"],
        )
    mock_git.infer_parent_branch.assert_called_once_with(
        "/repos/myrepo", "feature/child", ["main", "feature/parent"]
    )
    assert result == "feature/parent"


def test_returns_none_when_git_service_returns_none(vm):
    mock_git = MagicMock()
    mock_git.infer_parent_branch.return_value = None
    with patch("worktree_manager.github_vm.GitService", return_value=mock_git):
        result = vm.get_parent_branch_for_repo(
            "/repos/myrepo",
            branch="feature/child",
            remote_branches=["main"],
        )
    assert result is None


def test_returns_none_on_git_error(vm):
    mock_git = MagicMock()
    mock_git.infer_parent_branch.side_effect = Exception("git failed")
    with patch("worktree_manager.github_vm.GitService", return_value=mock_git):
        result = vm.get_parent_branch_for_repo(
            "/repos/myrepo",
            branch="feature/child",
            remote_branches=["main"],
        )
    assert result is None
