"""Tests for Iteration 3 — async WorkspaceProjectsPanel and PerRepoWorktreesView."""
import time as _time
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QComboBox, QLabel, QProgressBar, QPushButton

from worktree_manager.models import WorkspaceEntry, WorkspaceProject, WorktreeModel
from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_projects_vm(projects=None, entry_data=None):
    vm = MagicMock()
    vm._store.get_ui_pref.side_effect = lambda key, default: default
    vm._store.all_repos.return_value = {}
    vm.load_projects.return_value = projects or []
    vm.load_project_entries.return_value = entry_data or []
    return vm


def _make_workspace_panel(qtbot, vm=None):
    vm = vm or _make_projects_vm()
    panel = WorkspaceProjectsPanel(
        parent=None, vm=vm, on_close=lambda: None,
    )
    qtbot.addWidget(panel)
    return panel, vm


def _make_worktrees_vm():
    now = int(_time.time())
    vm = MagicMock()
    vm.load_worktree_view_data.return_value = {
        "worktrees": [
            WorktreeModel("/repos/proj", "main", True, now, False, False),
            WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
        ],
        "branch_status": [("main", True), ("fix/auth", True), ("hotfix/2", False)],
    }
    vm.is_protected_branch.return_value = False
    vm.has_uncommitted_changes.return_value = False
    return vm


def _make_worktrees_view(qtbot, vm=None):
    vm = vm or _make_worktrees_vm()
    view = PerRepoWorktreesView(
        vm=vm, repo_name="proj",
        on_cleanup=lambda: None, on_new=lambda: None,
    )
    qtbot.addWidget(view)
    return view, vm


# ── WorkspaceProjectsPanel — async load ──────────────────────────────────────

def test_workspace_panel_shows_progress_bar_while_loading(qtbot):
    project = WorkspaceProject("my-proj", [WorkspaceEntry("/wt/a"), WorkspaceEntry("/wt/b")])
    entry_data = [
        {"worktree_path": "/wt/a", "current_branch": "main", "branches": ["main"]},
        {"worktree_path": "/wt/b", "current_branch": "feat/x", "branches": ["main", "feat/x"]},
    ]
    vm = _make_projects_vm(projects=[project], entry_data=entry_data)

    # Delay load_project_entries so we can observe loading state
    import threading
    barrier = threading.Event()
    real_entries = entry_data[:]

    def slow_load(projects, on_progress=None):
        barrier.wait(timeout=3)
        return real_entries

    vm.load_project_entries.side_effect = slow_load

    panel, _ = _make_workspace_panel(qtbot, vm=vm)
    bars = panel.findChildren(QProgressBar)
    assert bars, "Expected a QProgressBar during load"

    barrier.set()
    qtbot.waitUntil(lambda: not panel._loading, timeout=3000)


def test_workspace_panel_renders_entries_after_load(qtbot):
    project = WorkspaceProject("my-proj", [WorkspaceEntry("/wt/a")])
    entry_data = [
        {"worktree_path": "/wt/a", "current_branch": "main", "branches": ["main", "feat"]},
    ]
    vm = _make_projects_vm(projects=[project], entry_data=entry_data)
    panel, _ = _make_workspace_panel(qtbot, vm=vm)
    qtbot.waitUntil(lambda: not panel._loading, timeout=3000)

    combos = panel.findChildren(QComboBox)
    assert combos, "Expected branch dropdowns after load"
    assert combos[0].findText("main") >= 0


def test_workspace_panel_empty_state_when_no_projects(qtbot):
    vm = _make_projects_vm(projects=[])
    panel, _ = _make_workspace_panel(qtbot, vm=vm)
    qtbot.waitUntil(lambda: not panel._loading, timeout=3000)

    labels = [lbl.text() for lbl in panel.findChildren(QLabel)]
    assert any("No projects" in t for t in labels)


def test_workspace_panel_load_project_entries_called_with_projects(qtbot):
    project = WorkspaceProject("p", [WorkspaceEntry("/wt/a")])
    entry_data = [{"worktree_path": "/wt/a", "current_branch": "main", "branches": ["main"]}]
    vm = _make_projects_vm(projects=[project], entry_data=entry_data)
    panel, vm = _make_workspace_panel(qtbot, vm=vm)
    qtbot.waitUntil(lambda: not panel._loading, timeout=3000)

    vm.load_project_entries.assert_called_once()
    call_args = vm.load_project_entries.call_args
    assert call_args[0][0] == [project] or call_args[1].get("projects") == [project]


# ── PerRepoWorktreesView — async load ────────────────────────────────────────

def test_per_repo_view_calls_load_worktree_view_data(qtbot):
    view, vm = _make_worktrees_view(qtbot)
    qtbot.waitUntil(lambda: not view._loading, timeout=3000)
    vm.load_worktree_view_data.assert_called()


def test_per_repo_view_renders_worktree_list_after_load(qtbot):
    view, _ = _make_worktrees_view(qtbot)
    qtbot.waitUntil(lambda: not view._loading, timeout=3000)

    labels = [lbl.text() for lbl in view.findChildren(QLabel)]
    assert any("fix-auth" in t or "fix/auth" in t for t in labels)
    assert any("(main)" in t for t in labels)


def test_per_repo_view_branch_dropdowns_present(qtbot):
    view, _ = _make_worktrees_view(qtbot)
    qtbot.waitUntil(lambda: not view._loading, timeout=3000)

    combos = view.findChildren(QComboBox)
    assert len(combos) == 2


def test_per_repo_view_branch_dropdown_lists_all_branches(qtbot):
    view, _ = _make_worktrees_view(qtbot)
    qtbot.waitUntil(lambda: not view._loading, timeout=3000)

    combo = view.findChildren(QComboBox)[0]
    values = [combo.itemText(i) for i in range(combo.count())]
    assert "main" in values
    assert "fix/auth" in values
    assert "hotfix/2" in values


def test_per_repo_view_delete_button_absent_for_main(qtbot):
    view, _ = _make_worktrees_view(qtbot)
    qtbot.waitUntil(lambda: not view._loading, timeout=3000)

    del_buttons = [b for b in view.findChildren(QPushButton) if b.text() == "✕"]
    assert len(del_buttons) == 1
