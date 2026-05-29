from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QPushButton, QListWidget, QLabel

from worktree_manager.ui.diff_panel import DiffPanel
from worktree_manager.diff_models import HistoryPoint, DiffFile


def _make_git(points=None, files=None):
    git = MagicMock()
    git.list_points.return_value = points or [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc", message="Merge"),
    ]
    git.diff_files.return_value = files or [
        DiffFile(path="src/foo.py", status="M"),
    ]
    return git


def _make_store(repos=None):
    store = MagicMock()
    store.all_repos.return_value = repos or ["/repos/myapp", "/repos/other"]
    store.get_repo.return_value = MagicMock(repo_path="/repos/myapp")
    return store


def _make_panel(qtbot, git=None, store=None, repos=None):
    from worktree_manager.diff_vm import DiffViewModel
    panel = DiffPanel(
        git_service=git or _make_git(),
        config_store=store or _make_store(repos=repos),
    )
    qtbot.addWidget(panel)
    return panel


# ── structure ─────────────────────────────────────────────────────────────────

def test_panel_has_repo_combo(qtbot):
    panel = _make_panel(qtbot)
    combos = panel.findChildren(QComboBox)
    assert len(combos) >= 1


def test_repo_combo_is_populated_from_store(qtbot):
    panel = _make_panel(qtbot, repos=["/repos/myapp", "/repos/other"])
    combo = panel._repo_combo
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert any("myapp" in l for l in labels)
    assert any("other" in l for l in labels)


def test_panel_starts_on_point_selector_screen(qtbot):
    panel = _make_panel(qtbot)
    from worktree_manager.ui.diff_point_selector import DiffPointSelector
    assert isinstance(panel._right_area.currentWidget(), DiffPointSelector)


# ── repo selection ────────────────────────────────────────────────────────────

def test_selecting_repo_loads_points_into_selector(qtbot):
    git = _make_git()
    panel = _make_panel(qtbot, git=git)
    panel._repo_combo.setCurrentIndex(0)
    from worktree_manager.ui.diff_point_selector import DiffPointSelector
    sel = panel._right_area.currentWidget()
    assert isinstance(sel, DiffPointSelector)
    assert sel._from_list.count() > 0


def test_selecting_different_repo_resets_to_point_selector(qtbot):
    git = _make_git()
    panel = _make_panel(qtbot, git=git, repos=["/repos/a", "/repos/b"])
    panel._repo_combo.setCurrentIndex(0)
    panel._vm.set_points("main", "working_tree_unstaged")
    panel._vm.load_diff_files()
    panel._right_area.setCurrentIndex(1)
    panel._repo_combo.setCurrentIndex(1)
    from worktree_manager.ui.diff_point_selector import DiffPointSelector
    assert isinstance(panel._right_area.currentWidget(), DiffPointSelector)


# ── compare flow ──────────────────────────────────────────────────────────────

def test_pressing_compare_switches_to_file_list(qtbot):
    panel = _make_panel(qtbot)
    panel._repo_combo.setCurrentIndex(0)
    from worktree_manager.ui.diff_point_selector import DiffPointSelector
    sel = panel._right_area.currentWidget()
    assert isinstance(sel, DiffPointSelector)
    sel._from_list.setCurrentRow(1)  # main
    sel._to_list.setCurrentRow(0)   # working_tree_unstaged
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    from worktree_manager.ui.diff_file_list import DiffFileList
    assert isinstance(panel._right_area.currentWidget(), DiffFileList)


def test_file_list_shows_diff_files_after_compare(qtbot):
    git = _make_git(files=[DiffFile(path="src/foo.py", status="M")])
    panel = _make_panel(qtbot, git=git)
    panel._repo_combo.setCurrentIndex(0)
    from worktree_manager.ui.diff_point_selector import DiffPointSelector
    sel = panel._right_area.currentWidget()
    sel._from_list.setCurrentRow(1)
    sel._to_list.setCurrentRow(0)
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    from worktree_manager.ui.diff_file_list import DiffFileList
    fl = panel._right_area.currentWidget()
    assert isinstance(fl, DiffFileList)
    texts = [fl._list_widget.item(i).text() for i in range(fl._list_widget.count())]
    assert any("foo.py" in t for t in texts)


# ── change button ─────────────────────────────────────────────────────────────

def test_change_button_returns_to_point_selector(qtbot):
    panel = _make_panel(qtbot)
    panel._repo_combo.setCurrentIndex(0)
    from worktree_manager.ui.diff_point_selector import DiffPointSelector
    sel = panel._right_area.currentWidget()
    sel._from_list.setCurrentRow(1)
    sel._to_list.setCurrentRow(0)
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    change_btn = next(b for b in panel.findChildren(QPushButton) if "Change" in b.text())
    qtbot.mouseClick(change_btn, Qt.LeftButton)
    assert isinstance(panel._right_area.currentWidget(), DiffPointSelector)
