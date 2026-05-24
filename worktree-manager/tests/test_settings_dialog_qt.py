from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QSpinBox

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


def test_settings_dialog_prefills_storage_and_stale_days(qtbot):
    vm = _make_vm(storage="/x/y", stale_days=14)
    d = SettingsDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    entry = d.findChild(QLineEdit)
    assert entry.text() == "/x/y"
    spin = d.findChild(QSpinBox)
    assert spin.value() == 14


def test_settings_dialog_save_calls_vm_with_current_values(qtbot):
    vm = _make_vm()
    d = SettingsDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    d.findChild(QLineEdit).setText("/new/storage")
    d.findChild(QSpinBox).setValue(7)
    save = next(b for b in d.findChildren(QPushButton) if b.text() == "Save")
    qtbot.mouseClick(save, Qt.LeftButton)
    vm.save.assert_called_once_with(worktree_storage="/new/storage", stale_days=7)


def test_settings_dialog_cancel_does_not_call_vm(qtbot):
    vm = _make_vm()
    d = SettingsDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    cancel = next(b for b in d.findChildren(QPushButton) if b.text() == "Cancel")
    qtbot.mouseClick(cancel, Qt.LeftButton)
    vm.save.assert_not_called()


def test_settings_dialog_browse_updates_entry(qtbot):
    vm = _make_vm(storage="/orig")
    d = SettingsDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    browse = next(b for b in d.findChildren(QPushButton) if b.text() == "Browse")
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
               return_value="/chosen"):
        qtbot.mouseClick(browse, Qt.LeftButton)
    assert d.findChild(QLineEdit).text() == "/chosen"
