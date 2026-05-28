from pathlib import Path
from unittest.mock import MagicMock

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.worktree_mgmt_vm import WorktreeMgmtViewModel


def _make_store(repos=None):
    store = MagicMock()
    store.all_repos.return_value = repos or {}
    store.get_repo.return_value = MagicMock(stale_days=90)
    return store


def _make_git():
    return MagicMock()


def test_list_repos_returns_all_repo_paths(tmp_path):
    repo_a = str(tmp_path / "repo-a")
    repo_b = str(tmp_path / "repo-b")
    vm = WorktreeMgmtViewModel(
        config_store=_make_store({repo_a: {}, repo_b: {}}),
        git_service=_make_git(),
    )
    paths = vm.list_repos()
    assert set(paths) == {repo_a, repo_b}


def test_list_repos_empty_when_none_configured():
    vm = WorktreeMgmtViewModel(
        config_store=_make_store({}),
        git_service=_make_git(),
    )
    assert vm.list_repos() == []


def test_selected_repo_is_none_initially():
    vm = WorktreeMgmtViewModel(
        config_store=_make_store(),
        git_service=_make_git(),
    )
    assert vm.selected_repo() is None


def test_select_repo_updates_selection(tmp_path):
    repo = str(tmp_path / "repo-a")
    vm = WorktreeMgmtViewModel(
        config_store=_make_store({repo: {}}),
        git_service=_make_git(),
    )
    vm.select_repo(repo)
    assert vm.selected_repo() == repo


def test_per_repo_vm_returns_main_window_view_model(tmp_path):
    repo = str(tmp_path / "repo-a")
    store = _make_store({repo: {}})
    git = _make_git()
    vm = WorktreeMgmtViewModel(config_store=store, git_service=git)
    repo_vm = vm.per_repo_vm(repo)
    assert isinstance(repo_vm, MainWindowViewModel)


def test_per_repo_vm_is_bound_to_correct_repo(tmp_path):
    repo = str(tmp_path / "repo-a")
    store = _make_store({repo: {}})
    git = _make_git()
    vm = WorktreeMgmtViewModel(config_store=store, git_service=git)
    repo_vm = vm.per_repo_vm(repo)
    assert repo_vm._repo_path == repo
