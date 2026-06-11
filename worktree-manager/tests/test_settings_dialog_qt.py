from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton, QSpinBox

from worktree_manager.setup_settings_vm import SettingsViewModel
from worktree_manager.ui.settings_panel import SettingsDialog


def _make_vm(storage="/repos/proj-wt", stale_days=30):
    vm = MagicMock(spec=SettingsViewModel)
    vm.worktree_storage = storage
    vm.stale_days = stale_days
    return vm


def test_settings_dialog_is_qdialog(qtbot):
    d = SettingsDialog(parent=None, vm=_make_vm())
    qtbot.addWidget(d)
    assert isinstance(d, QDialog)


def test_settings_dialog_prefills_stale_days(qtbot):
    vm = _make_vm(storage="/x/y", stale_days=14)
    d = SettingsDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    spin = d.findChild(QSpinBox)
    assert spin.value() == 14


def test_settings_dialog_save_calls_vm_with_current_values(qtbot):
    # Worktree storage is now configured per-repo in the project operations
    # dialog, so Settings saves the storage unchanged from the view model.
    vm = _make_vm(storage="/orig")
    d = SettingsDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    d.findChild(QSpinBox).setValue(7)
    save = next(b for b in d.findChildren(QPushButton) if b.text() == "Save")
    qtbot.mouseClick(save, Qt.LeftButton)
    vm.save.assert_called_once_with(worktree_storage="/orig", stale_days=7)


def test_settings_dialog_cancel_does_not_call_vm(qtbot):
    vm = _make_vm()
    d = SettingsDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    cancel = next(b for b in d.findChildren(QPushButton) if b.text() == "Cancel")
    qtbot.mouseClick(cancel, Qt.LeftButton)
    vm.save.assert_not_called()


