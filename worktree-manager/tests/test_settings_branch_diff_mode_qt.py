import sys
sys.path.insert(0, "/Users/ahmedhhw/repos/dev-tools/worktree-manager")

import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from worktree_manager.ui.settings_panel import SettingsDialog

app = QApplication.instance() or QApplication(sys.argv)


def _make_vm():
    vm = MagicMock()
    vm.worktree_storage = "/tmp/wt"
    vm.stale_days = 30
    return vm


def test_settings_dialog_shows_branch_diff_mode_row():
    store = MagicMock()
    store.get_ui_pref.return_value = "zsh"
    store.get_branch_diff_mode.return_value = "merge_base"
    dlg = SettingsDialog(None, _make_vm(), store=store)
    assert hasattr(dlg, "_branch_diff_combo")
    assert dlg._branch_diff_combo.currentData() == "merge_base"


def test_settings_dialog_saves_branch_tip_mode():
    store = MagicMock()
    store.get_ui_pref.return_value = "zsh"
    store.get_branch_diff_mode.return_value = "merge_base"
    dlg = SettingsDialog(None, _make_vm(), store=store)
    idx = dlg._branch_diff_combo.findData("branch_tip")
    dlg._branch_diff_combo.setCurrentIndex(idx)
    dlg._save()
    store.set_branch_diff_mode.assert_called_once_with("branch_tip")


def test_settings_dialog_preselects_saved_mode():
    store = MagicMock()
    store.get_ui_pref.return_value = "zsh"
    store.get_branch_diff_mode.return_value = "branch_tip"
    dlg = SettingsDialog(None, _make_vm(), store=store)
    assert dlg._branch_diff_combo.currentData() == "branch_tip"
