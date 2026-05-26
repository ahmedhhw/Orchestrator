"""Tests for startup pattern UI fields in Add Command dialog and Manage Commands dialog."""
from unittest.mock import MagicMock, call

import pytest
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QPlainTextEdit

from worktree_manager.models import SavedCommand
from worktree_manager.ui.add_command_dialog import AddCommandDialog
from worktree_manager.ui.manage_commands_dialog import ManageCommandsDialog


# --- helpers ---

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


def _manage_dlg(qtbot, commands=None):
    vm = _vm(commands=commands or [])
    d = ManageCommandsDialog(parent=None, vm=vm)
    qtbot.addWidget(d)
    return d, vm


# --- AddCommandDialog ---

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
    # fill in name and command
    name_entry = next(e for e in d.findChildren(QLineEdit) if e is not d._pattern_entry)
    name_entry.setText("dev")
    d.findChild(QPlainTextEdit).setPlainText("npm run dev")
    d._pattern_entry.setText("ready on")
    next(b for b in d.findChildren(QPushButton) if b.text() == "Save").click()
    vm.save_command.assert_called_once_with("/repos/proj", "dev", "npm run dev", startup_pattern="ready on")


def test_add_dialog_save_with_empty_pattern_passes_none(qtbot):
    vm = _vm()
    d = _add_dlg(qtbot, vm=vm)
    name_entry = next(e for e in d.findChildren(QLineEdit) if e is not d._pattern_entry)
    name_entry.setText("dev")
    d.findChild(QPlainTextEdit).setPlainText("npm run dev")
    # leave pattern blank
    next(b for b in d.findChildren(QPushButton) if b.text() == "Save").click()
    vm.save_command.assert_called_once_with("/repos/proj", "dev", "npm run dev", startup_pattern=None)


# --- ManageCommandsDialog view row ---

def test_manage_dialog_view_row_shows_startup_pattern_when_set(qtbot):
    cmds = [SavedCommand(name="srv", command="npm run dev", startup_pattern="ready on")]
    d, _ = _manage_dlg(qtbot, commands=cmds)
    labels = [l.text() for l in d.findChildren(QLabel)]
    assert any("ready on" in l for l in labels)


def test_manage_dialog_view_row_no_pattern_label_when_unset(qtbot):
    cmds = [SavedCommand(name="srv", command="npm run dev", startup_pattern=None)]
    d, _ = _manage_dlg(qtbot, commands=cmds)
    labels = [l.text() for l in d.findChildren(QLabel)]
    # should not show an empty or "None" pattern label
    assert not any(l.strip() in ("", "None") and "pattern" in l.lower() for l in labels)


# --- ManageCommandsDialog edit row ---

def test_manage_dialog_edit_row_has_startup_pattern_field(qtbot):
    cmds = [SavedCommand(name="srv", command="npm run dev", startup_pattern="ready on")]
    d, vm = _manage_dlg(qtbot, commands=cmds)
    edit_btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Edit")
    edit_btn.click()
    labels = [l.text() for l in d.findChildren(QLabel)]
    assert any("pattern" in l.lower() for l in labels)


def test_manage_dialog_edit_row_prepopulates_startup_pattern(qtbot):
    cmds = [SavedCommand(name="srv", command="npm run dev", startup_pattern="ready on")]
    d, vm = _manage_dlg(qtbot, commands=cmds)
    edit_btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Edit")
    edit_btn.click()
    assert d._edit_pattern_entry is not None
    assert d._edit_pattern_entry.text() == "ready on"


def test_manage_dialog_edit_saves_updated_startup_pattern(qtbot):
    cmds = [SavedCommand(name="srv", command="npm run dev", startup_pattern="ready on")]
    d, vm = _manage_dlg(qtbot, commands=cmds)
    edit_btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Edit")
    edit_btn.click()
    d._edit_pattern_entry.setText("Server started")
    save_btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Save")
    save_btn.click()
    vm.save_command.assert_called_once_with("/repos/proj", "srv", "npm run dev", startup_pattern="Server started")


def test_manage_dialog_edit_saves_empty_pattern_as_none(qtbot):
    cmds = [SavedCommand(name="srv", command="npm run dev", startup_pattern="ready on")]
    d, vm = _manage_dlg(qtbot, commands=cmds)
    edit_btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Edit")
    edit_btn.click()
    d._edit_pattern_entry.setText("")
    save_btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Save")
    save_btn.click()
    vm.save_command.assert_called_once_with("/repos/proj", "srv", "npm run dev", startup_pattern=None)
