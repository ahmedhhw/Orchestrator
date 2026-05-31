from unittest.mock import patch, MagicMock
import pytest
from worktree_manager.git_service import GitService


def _make_git():
    return GitService()


def _run_two(merged_output, log_output):
    """Return side_effect that yields merged_output for the first _run call, log_output for the second."""
    calls = iter([merged_output, log_output])
    def side_effect(cmd, **kwargs):
        return next(calls)
    return side_effect


def test_returns_parent_branch_from_log(tmp_path):
    git = _make_git()
    log_output = "HEAD -> feature/foo\nmain\n"
    with patch.object(git, "_run", side_effect=_run_two("", log_output)):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "feature/foo")
    assert parent == "main"


def test_skips_current_branch_in_log(tmp_path):
    git = _make_git()
    log_output = "HEAD -> feature/foo\nfeature/foo\nmain\n"
    with patch.object(git, "_run", side_effect=_run_two("", log_output)):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "feature/foo")
    assert parent == "main"


def test_returns_none_feature_when_same_as_parent(tmp_path):
    git = _make_git()
    log_output = "HEAD -> feature/foo\nmain\n"
    with patch.object(git, "_run", side_effect=_run_two("", log_output)):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "feature/foo")
    assert feature is None


def test_returns_feature_branch_when_parent_differs(tmp_path):
    git = _make_git()
    # parent is develop, feature/base is also in history; neither is merged into current
    log_output = "HEAD -> my-branch\ndevelop\nfeature/base\nmain\n"
    with patch.object(git, "_run", side_effect=_run_two("my-branch", log_output)):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "my-branch")
    assert parent == "develop"
    assert feature == "feature/base"


def test_returns_main_as_feature_when_parent_differs(tmp_path):
    git = _make_git()
    log_output = "HEAD -> my-branch\ndevelop\nmain\n"
    with patch.object(git, "_run", side_effect=_run_two("my-branch", log_output)):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "my-branch")
    assert parent == "develop"
    assert feature == "main"


def test_falls_back_to_main_when_log_empty(tmp_path):
    git = _make_git()
    with patch.object(git, "_run", side_effect=_run_two("", "")):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "feature/foo")
    assert parent == "main"
    assert feature is None


def test_falls_back_when_subprocess_error(tmp_path):
    import subprocess
    git = _make_git()
    with patch.object(git, "_run", side_effect=subprocess.CalledProcessError(1, "git")):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "feature/foo")
    assert parent == "main"
    assert feature is None


def test_deduplicates_feature_same_as_parent(tmp_path):
    git = _make_git()
    # main is first non-current branch AND also matches feature/main criteria
    log_output = "HEAD -> my-branch\nmain\n"
    with patch.object(git, "_run", side_effect=_run_two("my-branch", log_output)):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "my-branch")
    assert parent == "main"
    assert feature is None


def test_skips_merged_branches(tmp_path):
    git = _make_git()
    # filterable_dropdown_5_30 and new_filterable_dropdown are merged into HEAD
    merged_output = "filterable_dropdown_5_30\nnew_filterable_dropdown\nmain\n"
    log_output = "HEAD -> main\nfilterable_dropdown_5_30\norigin/main, origin/HEAD, new_filterable_dropdown\n"
    with patch.object(git, "_run", side_effect=_run_two(merged_output, log_output)):
        parent, feature = git.infer_branch_suggestions(str(tmp_path), "main")
    # On main with no non-merged non-current parent, falls back to (None, None)
    assert parent is None
    assert feature is None
