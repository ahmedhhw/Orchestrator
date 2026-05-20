import pytest
from unittest.mock import MagicMock
from worktree_manager.config_store import ConfigStore
from worktree_manager.git_service import GitService
from worktree_manager.models import RepoConfig
from worktree_manager.landing_screen import LandingScreenViewModel


@pytest.fixture
def store(tmp_path):
    s = ConfigStore(tmp_path / "config.json")
    for path, ts in [
        ("/repos/alpha", "2026-04-01T00:00:00"),
        ("/repos/beta",  "2026-05-01T00:00:00"),
    ]:
        s.save_repo(RepoConfig(
            repo_path=path,
            worktree_storage=path + "-wt",
            stale_days=30,
            last_editor="cursor",
            last_editor_mode="reuse",
            last_opened=ts,
        ))
    return s


@pytest.fixture
def git():
    return MagicMock(spec=GitService)


@pytest.fixture
def vm(store, git):
    return LandingScreenViewModel(config_store=store, git_service=git)


def test_recent_repos_sorted_newest_first(vm):
    repos = vm.recent_repos()
    assert repos[0].repo_path == "/repos/beta"
    assert repos[1].repo_path == "/repos/alpha"


def test_validate_repo_valid(vm, git):
    git.is_valid_repo.return_value = True
    ok, err = vm.validate_repo("/repos/valid")
    assert ok is True
    assert err == ""


def test_validate_repo_invalid(vm, git):
    git.is_valid_repo.return_value = False
    ok, err = vm.validate_repo("/repos/not-a-repo")
    assert ok is False
    assert "not a git repository" in err.lower()


def test_validate_repo_empty_path(vm, git):
    ok, err = vm.validate_repo("")
    assert ok is False
    assert err != ""


def test_on_repo_selected_calls_callback(vm, git):
    git.is_valid_repo.return_value = True
    callback = MagicMock()
    vm.on_repo_selected("/repos/valid", callback)
    callback.assert_called_once_with("/repos/valid")


def test_on_repo_selected_does_not_call_callback_on_invalid(vm, git):
    git.is_valid_repo.return_value = False
    callback = MagicMock()
    vm.on_repo_selected("/repos/bad", callback)
    callback.assert_not_called()
