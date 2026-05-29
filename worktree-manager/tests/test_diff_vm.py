from unittest.mock import MagicMock

import pytest

from worktree_manager.diff_vm import DiffViewModel
from worktree_manager.diff_models import HistoryPoint, DiffFile


def _make_git(points=None, files=None):
    git = MagicMock()
    git.list_points.return_value = points or []
    git.diff_files.return_value = files or []
    return git


def _make_vm(git=None, store=None):
    return DiffViewModel(git_service=git or _make_git(), config_store=store or MagicMock())


# ── initial state ─────────────────────────────────────────────────────────────

def test_vm_has_no_repo_initially():
    vm = _make_vm()
    assert vm.repo_path is None


def test_vm_available_points_empty_initially():
    vm = _make_vm()
    assert vm.available_points == []


def test_vm_diff_files_empty_initially():
    vm = _make_vm()
    assert vm.diff_files == []


def test_vm_base_ref_none_initially():
    vm = _make_vm()
    assert vm.base_ref is None


def test_vm_target_ref_none_initially():
    vm = _make_vm()
    assert vm.target_ref is None


# ── set_repo ──────────────────────────────────────────────────────────────────

def test_set_repo_stores_path():
    vm = _make_vm()
    vm.set_repo("/repos/myapp")
    assert vm.repo_path == "/repos/myapp"


def test_set_repo_loads_points_from_git_service():
    pts = [HistoryPoint(kind="branch", label="main", short_sha="abc", message="")]
    git = _make_git(points=pts)
    vm = _make_vm(git=git)
    vm.set_repo("/repos/myapp")
    assert vm.available_points == pts
    git.list_points.assert_called_once_with("/repos/myapp")


def test_set_repo_clears_refs():
    vm = _make_vm()
    vm.set_repo("/repos/myapp")
    vm.set_points("abc", "def")
    vm.set_repo("/repos/other")
    assert vm.base_ref is None
    assert vm.target_ref is None


def test_set_repo_clears_diff_files():
    files = [DiffFile(path="foo.py", status="M")]
    git = _make_git(files=files)
    vm = _make_vm(git=git)
    vm.set_repo("/repos/myapp")
    vm.set_points("abc", "def")
    vm.load_diff_files()
    vm.set_repo("/repos/other")
    assert vm.diff_files == []


# ── set_points / load_diff_files ──────────────────────────────────────────────

def test_set_points_stores_refs():
    vm = _make_vm()
    vm.set_repo("/repo")
    vm.set_points("main", "working_tree_unstaged")
    assert vm.base_ref == "main"
    assert vm.target_ref == "working_tree_unstaged"


def test_load_diff_files_calls_git_service():
    files = [DiffFile(path="src/auth.py", status="M")]
    git = _make_git(files=files)
    vm = _make_vm(git=git)
    vm.set_repo("/repo")
    vm.set_points("main", "working_tree_unstaged")
    vm.load_diff_files()
    git.diff_files.assert_called_once_with("/repo", "main", "working_tree_unstaged")


def test_load_diff_files_stores_result():
    files = [DiffFile(path="src/auth.py", status="M"), DiffFile(path="src/utils.py", status="A")]
    git = _make_git(files=files)
    vm = _make_vm(git=git)
    vm.set_repo("/repo")
    vm.set_points("abc", "def")
    vm.load_diff_files()
    assert vm.diff_files == files


def test_load_diff_files_without_repo_raises():
    vm = _make_vm()
    with pytest.raises(RuntimeError):
        vm.load_diff_files()


def test_load_diff_files_without_refs_raises():
    vm = _make_vm()
    vm.set_repo("/repo")
    with pytest.raises(RuntimeError):
        vm.load_diff_files()
