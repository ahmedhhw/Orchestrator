import pytest
import sys
from unittest.mock import MagicMock
from worktree_manager.cli import parse_args, resolve_repo_path
from worktree_manager.git_service import GitService


def test_parse_args_no_argument():
    args = parse_args([])
    assert args.repo_path is None


def test_parse_args_with_path():
    args = parse_args(["/repos/proj"])
    assert args.repo_path == "/repos/proj"


def test_resolve_repo_path_valid(tmp_path):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = True
    repo = tmp_path / "myrepo"
    repo.mkdir()
    result = resolve_repo_path(str(repo), git)
    assert result == str(repo)


def test_resolve_repo_path_invalid(tmp_path, capsys):
    git = MagicMock(spec=GitService)
    git.is_valid_repo.return_value = False
    with pytest.raises(SystemExit):
        resolve_repo_path(str(tmp_path / "notarepo"), git)
    captured = capsys.readouterr()
    assert "not a git repository" in captured.err.lower()


def test_resolve_repo_path_none_returns_none():
    git = MagicMock(spec=GitService)
    result = resolve_repo_path(None, git)
    assert result is None


def _make_vm(candidates):
    vm = MagicMock()
    vm.all_cleanup_candidates.return_value = candidates
    return vm


def test_show_cleanup_opens_wizard_when_candidates_exist():
    from worktree_manager.models import CleanupCandidate
    import worktree_manager.cli as cli_mod
    from unittest.mock import patch
    vm = _make_vm([
        CleanupCandidate("chore/deps", "/wt/chore-deps", False, True, 0)
    ])
    with patch("worktree_manager.ui.cleanup_wizard.CleanupWizard") as MockWizard:
        with patch("tkinter.messagebox.showinfo") as mock_info:
            app = object.__new__(cli_mod.App)
            app._root = MagicMock()
            app._current_frame = MagicMock()
            app._show_cleanup(vm)
    MockWizard.assert_called_once()
    mock_info.assert_not_called()


def test_show_cleanup_shows_messagebox_when_empty():
    import worktree_manager.cli as cli_mod
    from unittest.mock import patch
    vm = _make_vm([])
    with patch("worktree_manager.ui.cleanup_wizard.CleanupWizard") as MockWizard:
        with patch("tkinter.messagebox.showinfo") as mock_info:
            app = object.__new__(cli_mod.App)
            app._root = MagicMock()
            app._current_frame = MagicMock()
            app._show_cleanup(vm)
    MockWizard.assert_not_called()
    mock_info.assert_called_once()
