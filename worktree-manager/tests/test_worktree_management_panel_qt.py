import time
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.worktree_management_panel import WorktreeManagementPanel
from worktree_manager.worktree_mgmt_vm import WorktreeMgmtViewModel


def _make_vm(repos=None, tmp_path=None):
    store = MagicMock()
    store.all_repos.return_value = repos or {}
    store.get_repo.return_value = MagicMock(stale_days=90)
    git = MagicMock()
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    return WorktreeMgmtViewModel(config_store=store, git_service=git)


def _make_panel(qtbot, vm=None, on_add_repo=None, on_refresh=None, on_cleanup=None):
    panel = WorktreeManagementPanel(
        vm=vm or _make_vm(),
        on_add_repo=on_add_repo or (lambda: None),
        on_refresh=on_refresh or (lambda: None),
        on_cleanup=on_cleanup or (lambda path: None),
    )
    qtbot.addWidget(panel)
    return panel


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def test_panel_has_add_repo_button(qtbot):
    panel = _make_panel(qtbot)
    assert any("Add Repo" in t for t in _button_texts(panel))


def test_panel_has_refresh_button(qtbot):
    panel = _make_panel(qtbot)
    assert any("Refresh" in t for t in _button_texts(panel))


def test_panel_shows_empty_state_when_no_repo_selected(qtbot):
    panel = _make_panel(qtbot)
    texts = _label_texts(panel)
    assert any("Select a repo" in t for t in texts)


def test_panel_shows_repo_names_in_dropdown(qtbot, tmp_path):
    repo_a = str(tmp_path / "repo-a")
    repo_b = str(tmp_path / "repo-b")
    vm = _make_vm(repos={repo_a: {}, repo_b: {}})
    panel = _make_panel(qtbot, vm=vm)
    combo = panel.findChild(QComboBox, "repo_combo")
    items = [combo.itemText(i) for i in range(combo.count())]
    assert any("repo-a" in t for t in items)
    assert any("repo-b" in t for t in items)


def test_selecting_repo_from_dropdown_hides_empty_state(qtbot, tmp_path):
    repo = str(tmp_path / "repo-a")
    vm = _make_vm(repos={repo: {}})
    panel = _make_panel(qtbot, vm=vm)
    combo = panel.findChild(QComboBox, "repo_combo")
    combo.setCurrentIndex(0)
    visible_texts = [lbl.text() for lbl in panel.findChildren(QLabel) if not lbl.isHidden()]
    assert not any("Select a repo" in t for t in visible_texts)


def test_add_repo_button_invokes_callback(qtbot):
    triggered: list = []
    panel = _make_panel(qtbot, on_add_repo=lambda: triggered.append(1))
    btn = next(b for b in panel.findChildren(QPushButton) if "Add Repo" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == [1]


def test_refresh_button_invokes_callback(qtbot):
    triggered: list = []
    panel = _make_panel(qtbot, on_refresh=lambda: triggered.append(1))
    btn = next(b for b in panel.findChildren(QPushButton) if "Refresh" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == [1]


def test_panel_populate_repos_updates_dropdown(qtbot, tmp_path):
    repo = str(tmp_path / "repo-a")
    vm = _make_vm(repos={repo: {}})
    panel = _make_panel(qtbot, vm=vm)
    combo = panel.findChild(QComboBox, "repo_combo")
    assert any("repo-a" in combo.itemText(i) for i in range(combo.count()))
