"""Tests that every userData-keyed combo in Iteration 2 is a FilterableComboBox."""
import pytest
from unittest.mock import MagicMock

from worktree_manager.ui.filterable_combo import FilterableComboBox


# ── DiffPanel ──────────────────────────────────────────────────────────────

def test_diff_panel_repo_combo_is_filterable(qtbot):
    from worktree_manager.ui.diff_panel import DiffPanel
    git = MagicMock()
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.return_value = "cursor"
    w = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(w)
    assert isinstance(w._repo_combo, FilterableComboBox)


def test_diff_panel_worktree_combo_is_filterable(qtbot):
    from worktree_manager.ui.diff_panel import DiffPanel
    git = MagicMock()
    store = MagicMock()
    store.all_repos.return_value = {}
    store.get_ui_pref.return_value = "cursor"
    w = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(w)
    assert isinstance(w._worktree_combo, FilterableComboBox)


# ── WorktreeManagementPanel ────────────────────────────────────────────────

def test_worktree_management_repo_combo_is_filterable(qtbot):
    from worktree_manager.ui.worktree_management_panel import WorktreeManagementPanel
    vm = MagicMock()
    vm.list_repos.return_value = []
    w = WorktreeManagementPanel(
        vm=vm,
        on_add_repo=lambda: None,
        on_refresh=lambda: None,
        on_cleanup=lambda: None,
    )
    qtbot.addWidget(w)
    assert isinstance(w._repo_combo, FilterableComboBox)


# ── BranchManagementPanel ──────────────────────────────────────────────────

def test_branch_management_repo_combo_is_filterable(qtbot):
    from worktree_manager.ui.branch_management_panel import BranchManagementPanel
    vm = MagicMock()
    vm.list_repos.return_value = []
    vm.list_branches.return_value = []
    w = BranchManagementPanel(vm=vm)
    qtbot.addWidget(w)
    w._switch_section("cleanup")
    assert isinstance(w._repo_combo, FilterableComboBox)


# ── CommandPane worktree combo ─────────────────────────────────────────────

def test_command_pane_wt_combo_is_filterable(qtbot):
    from worktree_manager.ui.command_pane import CommandPane
    handle = MagicMock()
    handle.cmd_name = "pytest"
    handle.repo_name = "myrepo"
    handle.worktree_path = "/repo/main"
    from worktree_manager.command_runner import RunStatus
    handle.status = RunStatus.STOPPED
    handle.output_lines = []
    w = CommandPane(
        parent=None,
        handle=handle,
        on_maximize=lambda: None,
        on_stop=lambda: None,
        on_restart=lambda: None,
    )
    qtbot.addWidget(w)
    assert isinstance(w._wt_combo, FilterableComboBox)


# ── LaunchDialog worktree combo ────────────────────────────────────────────

def test_launch_dialog_wt_combo_is_filterable(qtbot):
    from worktree_manager.ui.launch_dialog import LaunchDialog
    vm = MagicMock()
    vm.all_repos.return_value = {}
    vm.list_worktrees.return_value = []
    vm.get_last_used_repo.return_value = None
    d = LaunchDialog(parent=None, vm=vm, confirm_fn=lambda m: True)
    qtbot.addWidget(d)
    assert isinstance(d._wt_combo, FilterableComboBox)


# ── SettingsDialog editor combo ────────────────────────────────────────────

def test_settings_editor_combo_is_filterable(qtbot):
    from worktree_manager.ui.settings_panel import SettingsDialog
    vm = MagicMock()
    vm.worktree_storage = "/tmp"
    vm.stale_days = 30
    store = MagicMock()
    store.get_ui_pref.return_value = "cursor"
    d = SettingsDialog(parent=None, vm=vm, store=store)
    qtbot.addWidget(d)
    assert isinstance(d._editor_combo, FilterableComboBox)


def test_settings_editor_combo_current_data_works(qtbot):
    from worktree_manager.ui.settings_panel import SettingsDialog
    vm = MagicMock()
    vm.worktree_storage = "/tmp"
    vm.stale_days = 30
    store = MagicMock()
    store.get_ui_pref.return_value = "vscode"
    d = SettingsDialog(parent=None, vm=vm, store=store)
    qtbot.addWidget(d)
    assert d._editor_combo.currentData() == "vscode"
