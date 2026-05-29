"""Tests for DiffViewModel restore_hunks, undo_restore, and open_file."""
from unittest.mock import MagicMock, call, patch

import pytest

from worktree_manager.diff_vm import DiffViewModel
from worktree_manager.diff_models import DiffHunk, DiffFile


def _make_hunk(index=0, header="@@ -1,3 +1,4 @@"):
    return DiffHunk(
        index=index, header=header,
        lines=[" ctx", "-old", "+new"],
        old_start=1, old_count=3, new_start=1, new_count=4,
    )


def _make_vm(hunks=None, files=None, editor="cursor"):
    git = MagicMock()
    git.list_points.return_value = []
    git.diff_files.return_value = files or [DiffFile(path="src/foo.py", status="M")]
    git.diff_hunks.return_value = hunks or [_make_hunk()]
    git.apply_reverse_patch.return_value = "forward patch text"
    store = MagicMock()
    store.get_ui_pref.return_value = editor
    vm = DiffViewModel(git_service=git, config_store=store)
    vm.set_repo("/repos/proj")
    vm.set_points("main", "working_tree_unstaged")
    vm.load_diff_files()
    return vm, git, store


# ── restore_hunks ─────────────────────────────────────────────────────────────

def test_restore_hunks_calls_apply_reverse_patch():
    vm, git, _ = _make_vm()
    hunk = _make_hunk()
    git.diff_hunks.return_value = [hunk]
    vm.restore_hunks("src/foo.py", [0])
    git.apply_reverse_patch.assert_called_once()
    args = git.apply_reverse_patch.call_args[0]
    assert args[1] == "src/foo.py"


def test_restore_hunks_passes_selected_hunks_only():
    h0 = _make_hunk(index=0, header="@@ -1,3 +1,4 @@")
    h1 = _make_hunk(index=1, header="@@ -20,3 +21,4 @@")
    vm, git, _ = _make_vm(hunks=[h0, h1])
    git.diff_hunks.return_value = [h0, h1]
    vm.restore_hunks("src/foo.py", [1])
    passed_hunks = git.apply_reverse_patch.call_args[0][2]
    assert len(passed_hunks) == 1
    assert passed_hunks[0].index == 1


def test_restore_hunks_returns_forward_patch():
    vm, git, _ = _make_vm()
    git.diff_hunks.return_value = [_make_hunk()]
    result = vm.restore_hunks("src/foo.py", [0])
    assert result == "forward patch text"


def test_restore_hunks_refreshes_diff_files():
    vm, git, _ = _make_vm()
    git.diff_hunks.return_value = [_make_hunk()]
    vm.restore_hunks("src/foo.py", [0])
    assert git.diff_files.call_count == 2  # once from load_diff_files, once from refresh


def test_restore_hunks_uses_worktree_path_when_set():
    vm, git, _ = _make_vm()
    vm.set_worktree("/repos/proj-wt/feat")
    vm.set_points("main", "working_tree_unstaged")
    vm.restore_hunks("src/foo.py", [0])
    cwd_arg = git.apply_reverse_patch.call_args[0][0]
    assert cwd_arg == "/repos/proj-wt/feat"


def test_restore_hunks_raises_without_refs():
    git = MagicMock()
    git.list_points.return_value = []
    vm = DiffViewModel(git_service=git, config_store=MagicMock())
    vm.set_repo("/repos/proj")
    with pytest.raises(RuntimeError):
        vm.restore_hunks("src/foo.py", [0])


# ── undo_restore ──────────────────────────────────────────────────────────────

def test_undo_restore_calls_apply_patch():
    vm, git, _ = _make_vm()
    vm.undo_restore("src/foo.py", "forward patch text")
    git.apply_patch.assert_called_once()


def test_undo_restore_passes_forward_patch():
    vm, git, _ = _make_vm()
    vm.undo_restore("src/foo.py", "some patch")
    patch_arg = git.apply_patch.call_args[0][1]
    assert patch_arg == "some patch"


def test_undo_restore_refreshes_diff_files():
    vm, git, _ = _make_vm()
    initial_count = git.diff_files.call_count
    vm.undo_restore("src/foo.py", "patch text")
    assert git.diff_files.call_count == initial_count + 1


def test_undo_restore_uses_worktree_path_when_set():
    vm, git, _ = _make_vm()
    vm.set_worktree("/repos/proj-wt/feat")
    vm.set_points("main", "working_tree_unstaged")
    vm.undo_restore("src/foo.py", "patch")
    cwd_arg = git.apply_patch.call_args[0][0]
    assert cwd_arg == "/repos/proj-wt/feat"


# ── open_file ─────────────────────────────────────────────────────────────────

def test_open_file_reads_editor_pref_from_store():
    vm, git, store = _make_vm(editor="vscode")
    editor_svc = MagicMock()
    vm.open_file("src/foo.py", editor_service=editor_svc)
    store.get_ui_pref.assert_any_call("editor", "cursor")


def test_open_file_delegates_to_editor_service():
    vm, git, store = _make_vm(editor="cursor")
    editor_svc = MagicMock()
    vm.open_file("src/foo.py", editor_service=editor_svc)
    editor_svc.open_new.assert_called_once()


def test_open_file_passes_absolute_path_to_editor():
    vm, git, store = _make_vm(editor="cursor")
    vm.set_worktree("/repos/proj-wt/feat")
    editor_svc = MagicMock()
    vm.open_file("src/foo.py", editor_service=editor_svc)
    path_arg = editor_svc.open_new.call_args[0][0]
    assert path_arg.endswith("src/foo.py")
    assert path_arg.startswith("/")


def test_open_file_uses_configured_editor_string():
    vm, git, store = _make_vm(editor="vscode")
    editor_svc = MagicMock()
    vm.open_file("src/foo.py", editor_service=editor_svc)
    editor_arg = editor_svc.open_new.call_args[0][1]
    assert editor_arg == "vscode"


def test_open_file_uses_repo_path_when_no_worktree():
    vm, git, store = _make_vm(editor="cursor")
    editor_svc = MagicMock()
    vm.open_file("src/foo.py", editor_service=editor_svc)
    path_arg = editor_svc.open_new.call_args[0][0]
    assert "/repos/proj/src/foo.py" == path_arg
