"""Tests for startup pattern UI field in Add Command dialog."""
from unittest.mock import MagicMock

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QPlainTextEdit

from worktree_manager.models import SavedCommand
from worktree_manager.ui.add_command_dialog import AddCommandDialog


def _vm(commands=None):
    vm = MagicMock()
    vm.all_repos.return_value = {"/repos/proj": MagicMock()}
    vm.get_last_used_repo.return_value = "/repos/proj"
    vm.saved_commands.return_value = commands or []
    return vm


def _add_dlg(qtbot, vm=None):
    d = AddCommandDialog(parent=None, vm=vm or _vm(), initial_repo="/repos/proj")
    qtbot.addWidget(d)
    return d


def test_add_dialog_has_startup_pattern_field(qtbot):
    d = _add_dlg(qtbot)
    labels = [l.text() for l in d.findChildren(QLabel)]
    assert any("startup" in l.lower() or "pattern" in l.lower() for l in labels)


def test_add_dialog_startup_pattern_field_is_empty_by_default(qtbot):
    d = _add_dlg(qtbot)
    assert d._pattern_entry.text() == ""


def test_add_dialog_save_passes_startup_pattern_to_vm(qtbot):
    vm = _vm()
    d = _add_dlg(qtbot, vm=vm)
    d._name_entry.setText("dev")
    d.findChild(QPlainTextEdit).setPlainText("npm run dev")
    d._pattern_entry.setText("ready on")
    next(b for b in d.findChildren(QPushButton) if b.text() == "Save").click()
    vm.save_command.assert_called_once_with("/repos/proj", "dev", "npm run dev", startup_pattern="ready on")


def test_add_dialog_save_with_empty_pattern_passes_none(qtbot):
    vm = _vm()
    d = _add_dlg(qtbot, vm=vm)
    d._name_entry.setText("dev")
    d.findChild(QPlainTextEdit).setPlainText("npm run dev")
    next(b for b in d.findChildren(QPushButton) if b.text() == "Save").click()
    vm.save_command.assert_called_once_with("/repos/proj", "dev", "npm run dev", startup_pattern=None)
