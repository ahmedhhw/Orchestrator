from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from worktree_manager.diff_models import HistoryPoint
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.diff_panel import DiffPanel


def _worktrees(repo_path="/repos/proj"):
    import time
    now = int(time.time())
    return [
        WorktreeModel(path=repo_path, branch="main", is_main=True, last_commit_ts=now, is_merged=False, is_stale=False),
        WorktreeModel(path=repo_path + "-wt/feat", branch="feature/x", is_main=False, last_commit_ts=now, is_merged=False, is_stale=False),
    ]


def _make_panel(qtbot, repos=None, worktrees=None):
    git = MagicMock()
    git.list_points.return_value = []
    git.diff_files.return_value = []
    git.list_worktrees.return_value = worktrees or _worktrees()
    store = MagicMock()
    store.all_repos.return_value = repos or ["/repos/proj"]
    store.get_ui_pref.return_value = "cursor"
    panel = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(panel)
    return panel, git


# ── Worktree combo presence ───────────────────────────────────────────────────

def test_diff_panel_has_worktree_combo(qtbot):
    panel, _ = _make_panel(qtbot)
    assert hasattr(panel, "_worktree_combo")
    assert panel._worktree_combo is not None


def test_worktree_combo_has_object_name(qtbot):
    panel, _ = _make_panel(qtbot)
    combo = panel.findChild(QComboBox, "worktree_combo")
    assert combo is not None


# ── Worktree combo population ─────────────────────────────────────────────────

def test_worktree_combo_populated_on_repo_select(qtbot):
    panel, _ = _make_panel(qtbot)
    items = [panel._worktree_combo.itemText(i) for i in range(panel._worktree_combo.count())]
    assert len(items) == 2


def test_main_worktree_shows_as_main_label(qtbot):
    panel, _ = _make_panel(qtbot)
    items = [panel._worktree_combo.itemText(i) for i in range(panel._worktree_combo.count())]
    assert "(main)" in items


def test_non_main_worktree_shows_folder_name(qtbot):
    panel, _ = _make_panel(qtbot)
    items = [panel._worktree_combo.itemText(i) for i in range(panel._worktree_combo.count())]
    assert "feat" in items


def test_worktree_combo_stores_path_as_user_data(qtbot):
    panel, _ = _make_panel(qtbot)
    paths = [panel._worktree_combo.itemData(i) for i in range(panel._worktree_combo.count())]
    assert "/repos/proj" in paths
    assert "/repos/proj-wt/feat" in paths


# ── Git commands use worktree path ────────────────────────────────────────────

def test_list_points_called_with_worktree_path(qtbot):
    panel, git = _make_panel(qtbot)
    panel._worktree_combo.setCurrentIndex(1)
    git.list_points.assert_called_with("/repos/proj-wt/feat")


def test_diff_files_uses_worktree_path_as_cwd(qtbot):
    from worktree_manager.diff_models import HistoryPoint
    panel, git = _make_panel(qtbot, worktrees=_worktrees())
    git.list_points.return_value = [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc1234", message="Init"),
    ]
    panel._worktree_combo.setCurrentIndex(1)
    panel._point_selector.pre_select(from_ref="main", to_ref="working_tree_unstaged")
    panel._on_compare("main", "working_tree_unstaged")
    git.diff_files.assert_called_with("/repos/proj-wt/feat", "main", "working_tree_unstaged")


# ── show_diff / show_for_repo accept worktree_path ────────────────────────────

def test_show_diff_preselects_worktree_combo(qtbot):
    panel, _ = _make_panel(qtbot)
    panel.show_diff("/repos/proj", worktree_path="/repos/proj-wt/feat",
                    to_ref="working_tree_unstaged", from_ref=None)
    assert panel._worktree_combo.currentData() == "/repos/proj-wt/feat"


def test_show_for_repo_accepts_worktree_path(qtbot):
    panel, _ = _make_panel(qtbot)
    panel.show_for_repo("/repos/proj", worktree_path="/repos/proj-wt/feat")
    assert panel._worktree_combo.currentData() == "/repos/proj-wt/feat"


def test_show_diff_without_worktree_path_keeps_first_worktree(qtbot):
    panel, _ = _make_panel(qtbot)
    panel.show_diff("/repos/proj", worktree_path=None,
                    to_ref="working_tree_unstaged", from_ref=None)
    assert panel._worktree_combo.currentIndex() == 0


# ── Changing worktree reloads points ─────────────────────────────────────────

def test_changing_worktree_resets_to_point_selector(qtbot):
    panel, _ = _make_panel(qtbot)
    panel._worktree_combo.setCurrentIndex(1)
    assert panel._right_area.currentWidget() is panel._point_selector
