from unittest.mock import MagicMock

from worktree_manager.diff_models import DiffFile, HistoryPoint
from worktree_manager.diff_vm import DiffViewModel


def _make_vm(git=None):
    git = git or MagicMock()
    git.list_points.return_value = []
    git.diff_files.return_value = []
    return DiffViewModel(git_service=git, config_store=MagicMock()), git


def test_set_worktree_stores_worktree_path():
    vm, _ = _make_vm()
    vm.set_repo("/repos/proj")
    vm.set_worktree("/repos/proj-wt/feat")
    assert vm.worktree_path == "/repos/proj-wt/feat"


def test_set_worktree_calls_list_points_with_worktree_path():
    vm, git = _make_vm()
    vm.set_repo("/repos/proj")
    vm.set_worktree("/repos/proj-wt/feat")
    git.list_points.assert_called_with("/repos/proj-wt/feat")


def test_load_diff_files_uses_worktree_path():
    files = [DiffFile(path="foo.py", status="M")]
    git = MagicMock()
    git.list_points.return_value = []
    git.diff_files.return_value = files
    vm = DiffViewModel(git_service=git, config_store=MagicMock())
    vm.set_repo("/repos/proj")
    vm.set_worktree("/repos/proj-wt/feat")
    vm.set_points("main", "working_tree_unstaged")
    vm.load_diff_files()
    git.diff_files.assert_called_once_with("/repos/proj-wt/feat", "main", "working_tree_unstaged")


def test_set_worktree_resets_points():
    vm, _ = _make_vm()
    vm.set_repo("/repos/proj")
    vm.set_worktree("/repos/proj-wt/feat")
    vm.set_points("main", "working_tree_unstaged")
    vm.set_worktree("/repos/proj")
    assert vm.base_ref is None
    assert vm.target_ref is None


def test_worktree_path_none_initially():
    vm, _ = _make_vm()
    assert vm.worktree_path is None


def test_load_diff_files_falls_back_to_repo_path_when_no_worktree():
    files = [DiffFile(path="foo.py", status="M")]
    git = MagicMock()
    git.list_points.return_value = []
    git.diff_files.return_value = files
    vm = DiffViewModel(git_service=git, config_store=MagicMock())
    vm.set_repo("/repos/proj")
    vm.set_points("main", "working_tree_unstaged")
    vm.load_diff_files()
    git.diff_files.assert_called_once_with("/repos/proj", "main", "working_tree_unstaged")
