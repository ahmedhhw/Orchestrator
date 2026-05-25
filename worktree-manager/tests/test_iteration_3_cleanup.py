"""Verify all legacy CTk sources and dead code for Iteration 3 are deleted."""
import os


def _tests_dir():
    return os.path.dirname(__file__)


def _project_root():
    return os.path.dirname(_tests_dir())


def test_legacy_cleanup_admin_mode_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_cleanup_wizard_admin_mode.py"))


def test_legacy_cleanup_protected_branches_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_cleanup_protected_branches.py"))


def test_legacy_cleanup_wizard_iter0_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_cleanup_wizard_iter0.py"))


def test_legacy_cleanup_wizard_merged_into_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_cleanup_wizard_merged_into.py"))


def test_legacy_cleanup_wizard_toggle_buttons_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_cleanup_wizard_toggle_buttons.py"))


def test_legacy_cleanup_wizard_merged_subgroups_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_cleanup_wizard_merged_subgroups.py"))


def test_legacy_new_project_dialog_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_new_project_dialog.py"))


def test_legacy_project_operations_dialog_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_project_operations_dialog.py"))


def test_legacy_workspace_projects_panel_test_deleted():
    assert not os.path.exists(os.path.join(_tests_dir(), "test_workspace_projects_panel.py"))


def test_dead_new_project_dialog_source_deleted():
    assert not os.path.exists(os.path.join(
        _project_root(), "worktree_manager", "ui", "new_project_dialog.py",
    ))


def test_scroll_fix_module_deleted():
    assert not os.path.exists(os.path.join(
        _project_root(), "worktree_manager", "scroll_fix.py",
    ))
