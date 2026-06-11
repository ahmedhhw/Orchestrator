import time
from unittest.mock import MagicMock

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QSplitter

from worktree_manager.models import WorktreeModel
from worktree_manager.ui.worktree_management_panel import WorktreeManagementPanel
from worktree_manager.worktree_mgmt_vm import WorktreeMgmtViewModel


def _repos_dict(paths):
    return {p: {} for p in paths}


def _make_vm(repos=None):
    store = MagicMock()
    paths = repos if repos is not None else ["/repos/proj", "/repos/other"]
    store.all_repos.return_value = _repos_dict(paths)
    store.get_repo.return_value = MagicMock(stale_days=90)
    git = MagicMock()
    now = int(time.time())
    git.list_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
    ]
    return WorktreeMgmtViewModel(config_store=store, git_service=git)


def _make_panel(qtbot, vm=None, **kwargs):
    panel = WorktreeManagementPanel(
        vm=vm or _make_vm(),
        on_add_repo=kwargs.get("on_add_repo", lambda: None),
        on_refresh=kwargs.get("on_refresh", lambda: None),
        on_cleanup=kwargs.get("on_cleanup", lambda path: None),
    )
    qtbot.addWidget(panel)
    return panel


def test_panel_has_repo_dropdown(qtbot):
    panel = _make_panel(qtbot)
    combos = panel.findChildren(QComboBox)
    repo_combos = [c for c in combos if c.objectName() == "repo_combo"]
    assert len(repo_combos) == 1


def test_repo_dropdown_is_populated_with_repos(qtbot):
    vm = _make_vm(repos=["/repos/alpha", "/repos/beta"])

    panel = _make_panel(qtbot, vm=vm)
    combo = panel.findChild(QComboBox, "repo_combo")
    assert combo is not None
    items = [combo.itemText(i) for i in range(combo.count())]
    assert "alpha" in items
    assert "beta" in items


def test_no_left_pane_splitter(qtbot):
    panel = _make_panel(qtbot)
    splitters = panel.findChildren(QSplitter)
    assert len(splitters) == 0


def test_panel_still_has_add_repo_button(qtbot):
    panel = _make_panel(qtbot)
    texts = [b.text() for b in panel.findChildren(QPushButton)]
    assert any("Add Repo" in t for t in texts)


def test_selecting_repo_shows_worktree_view(qtbot):
    vm = _make_vm(repos=["/repos/proj"])

    panel = _make_panel(qtbot, vm=vm)
    combo = panel.findChild(QComboBox, "repo_combo")
    assert combo is not None
    combo.setCurrentIndex(0)
    labels = [lbl.text() for lbl in panel.findChildren(QLabel)]
    assert any("Worktrees" in t or "proj" in t for t in labels)


def test_panel_shows_empty_state_when_no_repos(qtbot):
    vm = _make_vm(repos=[])

    panel = _make_panel(qtbot, vm=vm)
    labels = [lbl.text() for lbl in panel.findChildren(QLabel)]
    assert any("Add Repo" in t or "no repo" in t.lower() or "add" in t.lower() for t in labels)
