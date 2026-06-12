"""Tests that every text-keyed combo in Iteration 1 is a FilterableComboBox
and that currentTextChanged handlers have been moved to currentIndexChanged."""
import time
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.filterable_combo import FilterableComboBox


# ── helpers ────────────────────────────────────────────────────────────────

def _make_per_repo_vm():
    now = int(time.time())
    vm = MagicMock(spec=MainWindowViewModel)
    vm.load_worktree_view_data.return_value = {
        "worktrees": [
            WorktreeModel("/repos/proj", "main", True, now, False, False),
        ],
        "branch_status": [("main", True), ("dev", False)],
    }
    return vm


# ── MainWindow branch combo ────────────────────────────────────────────────

# ── PerRepoWorktreesView branch combo ─────────────────────────────────────

def test_per_repo_view_branch_combo_is_filterable(qtbot):
    from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView
    vm = _make_per_repo_vm()
    w = PerRepoWorktreesView(vm=vm, repo_name="proj", on_cleanup=lambda: None, on_new=lambda: None)
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: not w._loading, timeout=3000)
    combos = w.findChildren(FilterableComboBox)
    assert len(combos) >= 1


def test_per_repo_view_branch_combo_typing_does_not_trigger_switch(qtbot):
    from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView
    vm = _make_per_repo_vm()
    w = PerRepoWorktreesView(vm=vm, repo_name="proj", on_cleanup=lambda: None, on_new=lambda: None)
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: not w._loading, timeout=3000)
    combo = w.findChildren(FilterableComboBox)[0]
    combo.lineEdit().textEdited.emit("de")
    vm.switch_branch.assert_not_called()


# ── WorkspaceProjectsPanel branch combo ───────────────────────────────────

def test_workspace_projects_branch_combo_is_filterable(qtbot):
    from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel
    vm = MagicMock()
    vm.list_projects.return_value = []
    w = WorkspaceProjectsPanel(parent=None, vm=vm, on_close=lambda: None, confirm_fn=lambda m: True)
    qtbot.addWidget(w)
    w._add_entry_row("/repo/wt", precomputed={"current_branch": "main", "branches": ["main", "dev"]})
    combos = w.findChildren(FilterableComboBox)
    assert len(combos) >= 1


# ── AddCommandDialog repo combo ────────────────────────────────────────────

def test_add_command_dialog_repo_combo_is_filterable(qtbot):
    from worktree_manager.ui.add_command_dialog import AddCommandDialog
    vm = MagicMock()
    vm.all_repos.return_value = {"/repo/a": MagicMock(), "/repo/b": MagicMock()}
    vm.get_last_used_repo.return_value = None
    d = AddCommandDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    assert isinstance(d._repo_combo, FilterableComboBox)


# ── LaunchDialog repo combo ────────────────────────────────────────────────

def test_launch_dialog_repo_combo_is_filterable(qtbot):
    from worktree_manager.ui.launch_dialog import LaunchDialog
    vm = MagicMock()
    vm.all_repos.return_value = {}
    vm.list_worktrees.return_value = []
    vm.get_last_used_repo.return_value = None
    d = LaunchDialog(parent=None, vm=vm, confirm_fn=lambda m: True)
    qtbot.addWidget(d)
    assert isinstance(d._repo_combo, FilterableComboBox)


def test_launch_dialog_repo_combo_typing_does_not_call_on_repo_changed(qtbot):
    from worktree_manager.ui.launch_dialog import LaunchDialog
    vm = MagicMock()
    vm.all_repos.return_value = {"/repo/a": MagicMock()}
    vm.list_worktrees.return_value = []
    vm.get_last_used_repo.return_value = None
    d = LaunchDialog(parent=None, vm=vm, confirm_fn=lambda m: True)
    qtbot.addWidget(d)
    vm.list_worktrees.reset_mock()
    d._repo_combo.lineEdit().textEdited.emit("rep")
    vm.list_worktrees.assert_not_called()


# ── ProjectOperationsDialog repo combo ────────────────────────────────────

def test_project_operations_repo_combo_is_filterable(qtbot):
    from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
    vm = MagicMock()
    vm.list_worktrees.return_value = []
    vm.all_branches.return_value = []
    repos = {"/repo/a": MagicMock()}
    d = ProjectOperationsDialog(parent=None, vm=vm, repos=repos, on_create=lambda *a: None)
    qtbot.addWidget(d)
    assert isinstance(d._repo_combo, FilterableComboBox)


def test_project_operations_repo_combo_typing_does_not_load_worktrees(qtbot):
    from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
    vm = MagicMock()
    vm.list_worktrees.return_value = []
    vm.all_branches.return_value = []
    repos = {"/repo/a": MagicMock()}
    d = ProjectOperationsDialog(parent=None, vm=vm, repos=repos, on_create=lambda *a: None)
    qtbot.addWidget(d)
    vm.list_worktrees.reset_mock()
    d._repo_combo.lineEdit().textEdited.emit("rep")
    vm.list_worktrees.assert_not_called()


def test_project_operations_branch_combo_is_filterable(qtbot):
    from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
    vm = MagicMock()
    wt = MagicMock()
    wt.path = "/repo/a/wt"
    wt.branch = "main"
    wt.is_main = True
    wt.has_uncommitted = False
    vm.list_worktrees.return_value = [wt]
    vm.all_branches.return_value = ["main", "dev"]
    vm.switch_branch_in_project = MagicMock()
    repos = {"/repo/a": MagicMock()}
    d = ProjectOperationsDialog(parent=None, vm=vm, repos=repos, on_create=lambda *a: None)
    qtbot.addWidget(d)
    branch_combos = [c for c in d.findChildren(FilterableComboBox) if c is not d._repo_combo]
    assert len(branch_combos) >= 1


def test_project_operations_branch_combo_typing_does_not_switch_branch(qtbot):
    from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog
    vm = MagicMock()
    wt = MagicMock()
    wt.path = "/repo/a/wt"
    wt.branch = "main"
    wt.is_main = True
    wt.has_uncommitted = False
    vm.list_worktrees.return_value = [wt]
    vm.all_branches.return_value = ["main", "dev"]
    vm.switch_branch_in_project = MagicMock()
    repos = {"/repo/a": MagicMock()}
    d = ProjectOperationsDialog(parent=None, vm=vm, repos=repos, on_create=lambda *a: None)
    qtbot.addWidget(d)
    branch_combos = [c for c in d.findChildren(FilterableComboBox) if c is not d._repo_combo]
    branch_combos[0].lineEdit().textEdited.emit("de")
    vm.switch_branch_in_project.assert_not_called()


# ── SettingsDialog shell combo ─────────────────────────────────────────────

def test_settings_shell_combo_is_filterable(qtbot):
    from worktree_manager.ui.settings_panel import SettingsDialog
    vm = MagicMock()
    vm.worktree_storage = "/tmp"
    vm.stale_days = 30
    store = MagicMock()
    store.get_ui_pref.return_value = "zsh"
    d = SettingsDialog(parent=None, vm=vm, store=store)
    qtbot.addWidget(d)
    assert isinstance(d._shell_combo, FilterableComboBox)


# ── CreateDialog existing-branch combo ────────────────────────────────────

def test_create_dialog_existing_combo_is_filterable(qtbot):
    from worktree_manager.ui.create_dialog import CreateDialog
    d = CreateDialog(
        parent=None,
        branches=["main"],
        existing_branches=["fix/auth", "fix/login"],
        on_create=lambda *a: None,
    )
    qtbot.addWidget(d)
    assert isinstance(d._existing_combo, FilterableComboBox)


def test_create_dialog_existing_combo_typing_does_not_update_var(qtbot):
    from worktree_manager.ui.create_dialog import CreateDialog
    d = CreateDialog(
        parent=None,
        branches=["main"],
        existing_branches=["fix/auth", "fix/login"],
        on_create=lambda *a: None,
    )
    qtbot.addWidget(d)
    initial = d._existing_var.get()
    d._existing_combo.lineEdit().textEdited.emit("fix")
    assert d._existing_var.get() == initial


def test_create_dialog_existing_var_reflects_committed_selection(qtbot):
    from worktree_manager.ui.create_dialog import CreateDialog
    d = CreateDialog(
        parent=None,
        branches=["main"],
        existing_branches=["fix/auth", "fix/login"],
        on_create=lambda *a: None,
    )
    qtbot.addWidget(d)
    d._existing_combo._on_completer_activated("fix/login")
    assert d._existing_var.get() == "fix/login"
