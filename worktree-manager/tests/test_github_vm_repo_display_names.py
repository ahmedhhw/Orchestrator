import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_vm import GitHubViewModel
from worktree_manager.models import RepoConfig


def _repo_cfg(path):
    return RepoConfig(
        repo_path=path,
        worktree_storage=path + "/.worktrees",
        stale_days=14, last_editor="code",
        last_editor_mode="reuse", last_opened=0, commands=[],
    )


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
        return GitHubViewModel(store=store)


def test_display_names_maps_basename_to_full_path(vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    result = vm.list_open_pr_repos_display()
    assert result == {"alpha": "/repos/alpha"}


def test_display_names_multiple_repos(vm, store):
    store.save_repo(_repo_cfg("/repos/alpha"))
    store.save_repo(_repo_cfg("/repos/beta"))
    result = vm.list_open_pr_repos_display()
    assert result == {"alpha": "/repos/alpha", "beta": "/repos/beta"}


def test_display_names_empty_when_no_repos(vm):
    result = vm.list_open_pr_repos_display()
    assert result == {}


def test_display_names_collision_uses_full_path_as_key(vm, store):
    # Two repos with the same basename in different parent dirs
    store.save_repo(_repo_cfg("/work/myrepo"))
    store.save_repo(_repo_cfg("/personal/myrepo"))
    result = vm.list_open_pr_repos_display()
    # Both must be reachable — keys must be distinct
    assert len(result) == 2
    assert set(result.values()) == {"/work/myrepo", "/personal/myrepo"}
