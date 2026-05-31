from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from worktree_manager.ui.diff_panel import DiffPanel
from worktree_manager.config_store import ConfigStore
from worktree_manager.diff_models import HistoryPoint, DiffFile


def _make_git(tmp_path):
    svc = MagicMock()
    svc.list_worktrees.return_value = []
    svc.list_points.return_value = [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc1234", message="Main"),
        HistoryPoint(kind="branch", label="feature/x", short_sha="def5678", message="Feature"),
    ]
    return svc


def _make_panel(qtbot, tmp_path):
    store = ConfigStore(path=tmp_path / "config.json")
    # seed a repo
    from worktree_manager.models import RepoConfig
    store.save_repo(RepoConfig(
        repo_path=str(tmp_path),
        worktree_storage=str(tmp_path / "worktrees"),
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="project",
        last_opened=0,
    ))
    git = _make_git(tmp_path)
    git.list_worktrees.return_value = [
        MagicMock(path=str(tmp_path), is_main=True),
    ]
    panel = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(panel)
    return panel, store, str(tmp_path)


def test_diff_pref_persisted_on_compare(qtbot, tmp_path):
    panel, store, repo_path = _make_panel(qtbot, tmp_path)

    panel._vm.base_ref = "main"
    panel._vm.target_ref = "working_tree_unstaged"
    panel._vm.repo_path = repo_path
    panel._vm.load_diff_files = MagicMock(return_value=[])

    panel._on_compare("main", "working_tree_unstaged")

    pref = store.get_diff_pref(repo_path)
    assert pref is not None
    # Raw ref stored (not display label) so prefs are mode-agnostic
    assert pref["from_ref"] == "main"
    assert pref["to_ref"] == "working_tree_unstaged"


def test_diff_pref_pre_selects_on_worktree_load(qtbot, tmp_path):
    panel, store, repo_path = _make_panel(qtbot, tmp_path)
    store.set_diff_pref(repo_path, "feature/x", "working_tree_unstaged")

    panel._load_worktree(str(tmp_path))

    from_item = panel._point_selector._from_list.currentItem()
    to_item = panel._point_selector._to_list.currentItem()
    assert from_item is not None
    # In merge-base mode the list shows "feature/x (merge base)"
    assert "feature/x" in from_item.text()
    assert to_item is not None
    assert to_item.data(Qt.UserRole) == "working_tree_unstaged"
