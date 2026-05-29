"""Tests for GitService.diff_hunks() — parses unified diff output into DiffHunk list."""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from worktree_manager.git_service import GitService
from worktree_manager.diff_models import DiffHunk


SAMPLE_DIFF = """\
diff --git a/src/auth.py b/src/auth.py
index abc1234..def5678 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,7 +10,9 @@ def login(user, pwd):
     validate(user)
-    old_call()
+    new_call()
+    audit_log(user)
     return token()
@@ -25,4 +27,4 @@ def logout(user):
     cleanup()
-    old_cleanup(user)
+    new_cleanup(user)
"""

SINGLE_HUNK_DIFF = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@ class Foo:
 line1
-line2
+line2_new
+line3_new
 line4
"""


def _make_git():
    return GitService()


def _git_with_output(output: str):
    git = _make_git()
    git._run = MagicMock(return_value=output)
    return git


# ── basic parsing ──────────────────────────────────────────────────────────────

def test_diff_hunks_returns_list():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    assert isinstance(result, list)


def test_diff_hunks_returns_correct_count():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    assert len(result) == 2


def test_diff_hunks_have_sequential_indices():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    assert [h.index for h in result] == [0, 1]


def test_diff_hunks_parse_header():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    assert "@@ -10,7 +10,9 @@" in result[0].header
    assert "@@ -25,4 +27,4 @@" in result[1].header


def test_diff_hunks_parse_old_start():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    assert result[0].old_start == 10
    assert result[1].old_start == 25


def test_diff_hunks_parse_old_count():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    assert result[0].old_count == 7
    assert result[1].old_count == 4


def test_diff_hunks_parse_new_start():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    assert result[0].new_start == 10
    assert result[1].new_start == 27


def test_diff_hunks_parse_new_count():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    assert result[0].new_count == 9
    assert result[1].new_count == 4


def test_diff_hunks_include_diff_lines():
    git = _git_with_output(SAMPLE_DIFF)
    result = git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    lines = result[0].lines
    assert any(l.startswith("-") for l in lines)
    assert any(l.startswith("+") for l in lines)


def test_diff_hunks_returns_empty_for_no_diff():
    git = _git_with_output("")
    result = git.diff_hunks("/repo", "main", "main", "src/auth.py")
    assert result == []


def test_diff_hunks_single_hunk():
    git = _git_with_output(SINGLE_HUNK_DIFF)
    result = git.diff_hunks("/repo", "abc", "def", "foo.py")
    assert len(result) == 1
    assert result[0].index == 0
    assert result[0].old_start == 1
    assert result[0].old_count == 3
    assert result[0].new_start == 1
    assert result[0].new_count == 4


# ── git command dispatching ────────────────────────────────────────────────────

def test_diff_hunks_uses_working_tree_unstaged_command():
    git = _make_git()
    git._run = MagicMock(return_value="")
    git.diff_hunks("/repo", "main", "working_tree_unstaged", "src/auth.py")
    cmd = git._run.call_args[0][0]
    assert "diff" in cmd
    assert "--cached" not in cmd
    assert "main" in cmd
    assert "src/auth.py" in cmd


def test_diff_hunks_uses_staged_command():
    git = _make_git()
    git._run = MagicMock(return_value="")
    git.diff_hunks("/repo", "main", "working_tree_staged", "src/auth.py")
    cmd = git._run.call_args[0][0]
    assert "--cached" in cmd


def test_diff_hunks_uses_commit_to_commit_command():
    git = _make_git()
    git._run = MagicMock(return_value="")
    git.diff_hunks("/repo", "abc123", "def456", "src/auth.py")
    cmd = git._run.call_args[0][0]
    assert "abc123" in cmd
    assert "def456" in cmd
    assert "--cached" not in cmd
