from unittest.mock import MagicMock
import pytest
from worktree_manager.diff_vm import DiffViewModel
from worktree_manager.diff_models import HistoryPoint


def _make_points():
    return [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="working_tree_staged", label="Working tree (staged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc", message="init"),
        HistoryPoint(kind="branch", label="feature/foo", short_sha="def", message="foo"),
    ]


def _make_vm(parent="main", feature=None, last_pref=None):
    git = MagicMock()
    git.list_points.return_value = _make_points()
    git.infer_branch_suggestions.return_value = (parent, feature)
    git.checked_out_branch.return_value = "feature/bar"

    store = MagicMock()
    store.get_diff_pref.return_value = (
        {"from_ref": last_pref, "to_ref": "working_tree_unstaged"} if last_pref else None
    )

    vm = DiffViewModel(git_service=git, config_store=store)
    vm.set_repo("/repo")
    vm.set_worktree("/repo/worktrees/bar")
    return vm


# ── default_newer_ref ─────────────────────────────────────────────────────────

def test_default_newer_ref_is_working_tree_unstaged():
    vm = _make_vm()
    assert vm.default_newer_ref("/repo/worktrees/bar") == "working_tree_unstaged"


# ── default_older_ref ─────────────────────────────────────────────────────────

def test_default_older_ref_returns_inferred_parent():
    vm = _make_vm(parent="main")
    assert vm.default_older_ref("/repo/worktrees/bar") == "main"


def test_default_older_ref_returns_none_when_no_parent():
    git = MagicMock()
    git.list_points.return_value = _make_points()
    git.infer_branch_suggestions.return_value = (None, None)
    store = MagicMock()
    store.get_diff_pref.return_value = None
    vm = DiffViewModel(git_service=git, config_store=store)
    vm.set_repo("/repo")
    vm.set_worktree("/repo/worktrees/bar")
    assert vm.default_older_ref("/repo/worktrees/bar") is None


# ── suggested_newer_refs ─────────────────────────────────────────────────────

def test_suggested_newer_refs_contains_working_tree_unstaged():
    vm = _make_vm()
    refs = vm.suggested_newer_refs("/repo/worktrees/bar")
    assert "working_tree_unstaged" in refs


def test_suggested_newer_refs_working_tree_unstaged_is_first():
    vm = _make_vm()
    refs = vm.suggested_newer_refs("/repo/worktrees/bar")
    assert refs[0] == "working_tree_unstaged"


# ── suggested_older_refs ─────────────────────────────────────────────────────

def test_suggested_older_refs_contains_parent():
    vm = _make_vm(parent="main")
    refs = vm.suggested_older_refs("/repo/worktrees/bar", _make_points())
    assert "main" in refs


def test_suggested_older_refs_max_three():
    vm = _make_vm(parent="develop", feature="feature/foo", last_pref="main")
    refs = vm.suggested_older_refs("/repo/worktrees/bar", _make_points())
    assert len(refs) <= 3


def test_suggested_older_refs_deduplicates():
    # parent == feature_or_main, only one entry
    vm = _make_vm(parent="main", feature=None, last_pref=None)
    refs = vm.suggested_older_refs("/repo/worktrees/bar", _make_points())
    assert refs.count("main") == 1


def test_suggested_older_refs_includes_last_pref_when_different():
    vm = _make_vm(parent="develop", feature=None, last_pref="main")
    refs = vm.suggested_older_refs("/repo/worktrees/bar", _make_points())
    assert "main" in refs


def test_suggested_older_refs_excludes_last_pref_when_same_as_parent():
    vm = _make_vm(parent="main", feature=None, last_pref="main")
    refs = vm.suggested_older_refs("/repo/worktrees/bar", _make_points())
    assert refs.count("main") == 1


def test_suggested_older_refs_parent_is_first():
    vm = _make_vm(parent="develop", feature="feature/foo", last_pref="main")
    refs = vm.suggested_older_refs("/repo/worktrees/bar", _make_points())
    assert refs[0] == "develop"
