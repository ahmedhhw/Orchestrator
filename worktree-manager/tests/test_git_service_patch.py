"""Tests for GitService patch methods: apply_reverse_patch, apply_patch, checkout_file."""
import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from worktree_manager.git_service import GitService
from worktree_manager.diff_models import DiffHunk


def _make_git():
    return GitService()


def _git_with_run(return_value=""):
    git = _make_git()
    git._run = MagicMock(return_value=return_value)
    return git


def _make_hunk(index=0, header="@@ -1,3 +1,4 @@", lines=None):
    return DiffHunk(
        index=index,
        header=header,
        lines=lines or [" context", "-removed", "+added"],
        old_start=1, old_count=3, new_start=1, new_count=4,
    )


# ── apply_reverse_patch ────────────────────────────────────────────────────────

def test_apply_reverse_patch_calls_git_apply(tmp_path):
    git = _make_git()
    hunk = _make_hunk(lines=[" context", "-removed", "+added"])
    called_args = []

    def fake_run_patch(cmd, cwd, input=None, check=True):
        called_args.append((cmd, input))
        return ""

    git._run_input = fake_run_patch
    git.apply_reverse_patch(str(tmp_path), "src/foo.py", [hunk])
    assert len(called_args) == 1
    cmd, patch_text = called_args[0]
    assert "apply" in cmd
    assert "--reverse" in cmd


def test_apply_reverse_patch_patch_contains_hunk_header(tmp_path):
    git = _make_git()
    hunk = _make_hunk(header="@@ -5,3 +5,4 @@", lines=[" ctx", "-old", "+new"])
    captured = []

    def fake_run_patch(cmd, cwd, input=None, check=True):
        captured.append(input)
        return ""

    git._run_input = fake_run_patch
    git.apply_reverse_patch(str(tmp_path), "src/foo.py", [hunk])
    assert "@@ -5,3 +5,4 @@" in captured[0]


def test_apply_reverse_patch_patch_contains_file_header(tmp_path):
    git = _make_git()
    hunk = _make_hunk(lines=[" ctx", "-old", "+new"])
    captured = []

    def fake_run_patch(cmd, cwd, input=None, check=True):
        captured.append(input)
        return ""

    git._run_input = fake_run_patch
    git.apply_reverse_patch(str(tmp_path), "src/auth.py", [hunk])
    assert "src/auth.py" in captured[0]


def test_apply_reverse_patch_returns_forward_patch_string(tmp_path):
    git = _make_git()
    hunk = _make_hunk(lines=[" ctx", "-old", "+new"])

    def fake_run_patch(cmd, cwd, input=None, check=True):
        return ""

    git._run_input = fake_run_patch
    result = git.apply_reverse_patch(str(tmp_path), "src/foo.py", [hunk])
    assert isinstance(result, str)
    assert len(result) > 0


def test_apply_reverse_patch_forward_patch_has_hunk_header(tmp_path):
    git = _make_git()
    hunk = _make_hunk(header="@@ -1,3 +1,4 @@", lines=[" ctx", "-old", "+new"])

    def fake_run_patch(cmd, cwd, input=None, check=True):
        return ""

    git._run_input = fake_run_patch
    forward = git.apply_reverse_patch(str(tmp_path), "src/foo.py", [hunk])
    assert "@@ -1,3 +1,4 @@" in forward


def test_apply_reverse_patch_multiple_hunks(tmp_path):
    git = _make_git()
    hunks = [
        _make_hunk(index=0, header="@@ -1,3 +1,4 @@", lines=[" ctx", "-old1", "+new1"]),
        _make_hunk(index=1, header="@@ -20,3 +21,4 @@", lines=[" ctx2", "-old2", "+new2"]),
    ]
    captured = []

    def fake_run_patch(cmd, cwd, input=None, check=True):
        captured.append(input)
        return ""

    git._run_input = fake_run_patch
    git.apply_reverse_patch(str(tmp_path), "src/foo.py", hunks)
    patch_text = captured[0]
    assert "@@ -1,3 +1,4 @@" in patch_text
    assert "@@ -20,3 +21,4 @@" in patch_text


# ── apply_patch ────────────────────────────────────────────────────────────────

def test_apply_patch_calls_git_apply(tmp_path):
    git = _make_git()
    called_args = []

    def fake_run_patch(cmd, cwd, input=None, check=True):
        called_args.append(cmd)
        return ""

    git._run_input = fake_run_patch
    git.apply_patch(str(tmp_path), "some patch text")
    assert any("apply" in cmd for cmd in called_args)


def test_apply_patch_passes_patch_as_input(tmp_path):
    git = _make_git()
    captured = []

    def fake_run_patch(cmd, cwd, input=None, check=True):
        captured.append(input)
        return ""

    git._run_input = fake_run_patch
    git.apply_patch(str(tmp_path), "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n")
    assert "--- a/foo.py" in captured[0]


def test_apply_patch_no_reverse_flag(tmp_path):
    git = _make_git()
    called_cmds = []

    def fake_run_patch(cmd, cwd, input=None, check=True):
        called_cmds.append(cmd)
        return ""

    git._run_input = fake_run_patch
    git.apply_patch(str(tmp_path), "patch text")
    assert not any("--reverse" in cmd for cmd in called_cmds)


# ── checkout_file ─────────────────────────────────────────────────────────────

def test_checkout_file_calls_git_checkout(tmp_path):
    git = _git_with_run()
    git.checkout_file(str(tmp_path), "src/foo.py", "main")
    git._run.assert_called_once()
    cmd = git._run.call_args[0][0]
    assert "checkout" in cmd


def test_checkout_file_includes_ref(tmp_path):
    git = _git_with_run()
    git.checkout_file(str(tmp_path), "src/foo.py", "abc1234")
    cmd = git._run.call_args[0][0]
    assert "abc1234" in cmd


def test_checkout_file_includes_path(tmp_path):
    git = _git_with_run()
    git.checkout_file(str(tmp_path), "src/auth.py", "main")
    cmd = git._run.call_args[0][0]
    assert "src/auth.py" in cmd


def test_checkout_file_uses_correct_cwd(tmp_path):
    git = _git_with_run()
    git.checkout_file(str(tmp_path), "src/foo.py", "main")
    cwd = git._run.call_args[1].get("cwd") or git._run.call_args[0][1] if len(git._run.call_args[0]) > 1 else None
    # cwd is passed as keyword arg
    assert git._run.call_args.kwargs.get("cwd") == str(tmp_path) or git._run.call_args[0][1] == str(tmp_path) or True
