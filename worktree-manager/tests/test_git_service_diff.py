import subprocess
from unittest.mock import patch, MagicMock

import pytest

from worktree_manager.git_service import GitService
from worktree_manager.diff_models import HistoryPoint, DiffFile


@pytest.fixture
def svc():
    return GitService()


# ── list_points ──────────────────────────────────────────────────────────────

def test_list_points_starts_with_working_tree_entries(svc):
    with patch.object(svc, "_run", side_effect=_list_points_run_mock):
        points = svc.list_points("/repo")
    kinds = [p.kind for p in points[:2]]
    assert kinds == ["working_tree_unstaged", "working_tree_staged"]


def test_list_points_working_tree_unstaged_has_correct_label(svc):
    with patch.object(svc, "_run", side_effect=_list_points_run_mock):
        points = svc.list_points("/repo")
    wt = next(p for p in points if p.kind == "working_tree_unstaged")
    assert wt.label == "Working tree (unstaged)"
    assert wt.short_sha == ""


def test_list_points_working_tree_staged_has_correct_label(svc):
    with patch.object(svc, "_run", side_effect=_list_points_run_mock):
        points = svc.list_points("/repo")
    wt = next(p for p in points if p.kind == "working_tree_staged")
    assert wt.label == "Working tree (staged)"


def test_list_points_includes_branches(svc):
    with patch.object(svc, "_run", side_effect=_list_points_run_mock):
        points = svc.list_points("/repo")
    branch_points = [p for p in points if p.kind == "branch"]
    assert len(branch_points) == 2
    labels = [p.label for p in branch_points]
    assert "main" in labels
    assert "feature/login" in labels


def test_list_points_branches_have_sha_and_message(svc):
    with patch.object(svc, "_run", side_effect=_list_points_run_mock):
        points = svc.list_points("/repo")
    main_pt = next(p for p in points if p.kind == "branch" and p.label == "main")
    assert main_pt.short_sha == "abc1234"
    assert main_pt.message == "Merge PR #42"


def test_list_points_includes_recent_commits_up_to_20(svc):
    with patch.object(svc, "_run", side_effect=_list_points_run_mock):
        points = svc.list_points("/repo")
    commit_points = [p for p in points if p.kind == "commit"]
    assert len(commit_points) == 3


def test_list_points_order_is_working_tree_then_branches_then_commits(svc):
    with patch.object(svc, "_run", side_effect=_list_points_run_mock):
        points = svc.list_points("/repo")
    kinds = [p.kind for p in points]
    wt_indices = [i for i, k in enumerate(kinds) if k.startswith("working_tree")]
    branch_indices = [i for i, k in enumerate(kinds) if k == "branch"]
    commit_indices = [i for i, k in enumerate(kinds) if k == "commit"]
    assert max(wt_indices) < min(branch_indices)
    assert max(branch_indices) < min(commit_indices)


def test_list_points_returns_history_point_instances(svc):
    with patch.object(svc, "_run", side_effect=_list_points_run_mock):
        points = svc.list_points("/repo")
    assert all(isinstance(p, HistoryPoint) for p in points)


# ── diff_files ────────────────────────────────────────────────────────────────

def test_diff_files_between_two_commits_calls_git_diff_name_status(svc):
    with patch.object(svc, "_run", return_value="M\tsrc/foo.py\n") as mock_run:
        svc.diff_files("/repo", "abc1234", "def5678")
    mock_run.assert_called_once_with(
        ["git", "diff", "--name-status", "abc1234", "def5678"],
        cwd="/repo",
    )


def test_diff_files_to_working_tree_unstaged_omits_target(svc):
    with patch.object(svc, "_run", return_value="M\tsrc/foo.py\n") as mock_run:
        svc.diff_files("/repo", "abc1234", "working_tree_unstaged")
    mock_run.assert_any_call(
        ["git", "diff", "--name-status", "abc1234"],
        cwd="/repo",
    )


def test_diff_files_from_working_tree_unstaged_swaps_to_correct_git_command(svc):
    with patch.object(svc, "_run", return_value="M\tsrc/foo.py\n") as mock_run:
        svc.diff_files("/repo", "working_tree_unstaged", "abc1234")
    mock_run.assert_any_call(
        ["git", "diff", "--name-status", "abc1234"],
        cwd="/repo",
    )


def test_diff_files_from_working_tree_staged_swaps_to_correct_git_command(svc):
    with patch.object(svc, "_run", return_value="M\tsrc/foo.py\n") as mock_run:
        svc.diff_files("/repo", "working_tree_staged", "abc1234")
    mock_run.assert_called_once_with(
        ["git", "diff", "--name-status", "--cached", "abc1234"],
        cwd="/repo",
    )


def test_diff_files_unstaged_includes_untracked_files(svc):
    def _run_mock(cmd, cwd=None):
        if "--name-status" in cmd:
            return "M\tsrc/foo.py\n"
        if "ls-files" in cmd:
            return "new_file.py\nanother/new.py\n"
        return ""
    with patch.object(svc, "_run", side_effect=_run_mock):
        files = svc.diff_files("/repo", "abc1234", "working_tree_unstaged")
    paths = [f.path for f in files]
    assert "new_file.py" in paths
    assert "another/new.py" in paths


def test_diff_files_untracked_have_question_mark_status(svc):
    def _run_mock(cmd, cwd=None):
        if "--name-status" in cmd:
            return ""
        if "ls-files" in cmd:
            return "untracked.py\n"
        return ""
    with patch.object(svc, "_run", side_effect=_run_mock):
        files = svc.diff_files("/repo", "abc1234", "working_tree_unstaged")
    assert files[0].status == "?"


def test_diff_files_staged_does_not_include_untracked(svc):
    calls = []
    def _run_mock(cmd, cwd=None):
        calls.append(cmd)
        return "M\tsrc/foo.py\n"
    with patch.object(svc, "_run", side_effect=_run_mock):
        svc.diff_files("/repo", "abc1234", "working_tree_staged")
    assert not any("ls-files" in " ".join(c) for c in calls)


def test_diff_files_commit_to_commit_does_not_include_untracked(svc):
    calls = []
    def _run_mock(cmd, cwd=None):
        calls.append(cmd)
        return "M\tsrc/foo.py\n"
    with patch.object(svc, "_run", side_effect=_run_mock):
        svc.diff_files("/repo", "abc1234", "def5678")
    assert not any("ls-files" in " ".join(c) for c in calls)


def test_diff_files_to_working_tree_staged_uses_cached(svc):
    with patch.object(svc, "_run", return_value="M\tsrc/foo.py\n") as mock_run:
        svc.diff_files("/repo", "abc1234", "working_tree_staged")
    mock_run.assert_called_once_with(
        ["git", "diff", "--name-status", "--cached", "abc1234"],
        cwd="/repo",
    )


def test_diff_files_returns_diff_file_list(svc):
    with patch.object(svc, "_run", return_value="M\tsrc/foo.py\nA\tsrc/bar.py\nD\tsrc/old.py\n"):
        files = svc.diff_files("/repo", "abc1234", "def5678")
    assert all(isinstance(f, DiffFile) for f in files)
    assert len(files) == 3


def test_diff_files_parses_modified_status(svc):
    with patch.object(svc, "_run", return_value="M\tsrc/foo.py\n"):
        files = svc.diff_files("/repo", "abc1234", "def5678")
    assert files[0].path == "src/foo.py"
    assert files[0].status == "M"


def test_diff_files_parses_added_status(svc):
    with patch.object(svc, "_run", return_value="A\tsrc/new.py\n"):
        files = svc.diff_files("/repo", "abc1234", "def5678")
    assert files[0].status == "A"


def test_diff_files_parses_deleted_status(svc):
    with patch.object(svc, "_run", return_value="D\tsrc/gone.py\n"):
        files = svc.diff_files("/repo", "abc1234", "def5678")
    assert files[0].status == "D"


def test_diff_files_parses_renamed_status(svc):
    with patch.object(svc, "_run", return_value="R100\told/path.py\tnew/path.py\n"):
        files = svc.diff_files("/repo", "abc1234", "def5678")
    assert files[0].status == "R"
    assert files[0].path == "new/path.py"
    assert files[0].old_path == "old/path.py"


def test_diff_files_returns_empty_list_when_no_diff(svc):
    with patch.object(svc, "_run", return_value=""):
        files = svc.diff_files("/repo", "abc1234", "def5678")
    assert files == []


# ── helpers for mocking _run ─────────────────────────────────────────────────

_BRANCH_LOG_OUTPUT = (
    "main\tabc1234\tMerge PR #42\n"
    "feature/login\tdef5678\tAdd auth flow\n"
)

_COMMIT_LOG_OUTPUT = (
    "ghi9012\tFix tests\n"
    "jkl3456\tAdd unit tests\n"
    "mno7890\tInitial commit\n"
)


def _list_points_run_mock(cmd, cwd=None):
    if cmd[:3] == ["git", "log", "--branches"]:
        return _BRANCH_LOG_OUTPUT
    if cmd[:2] == ["git", "log"] and "--no-walk" not in cmd:
        return _COMMIT_LOG_OUTPUT
    return ""
