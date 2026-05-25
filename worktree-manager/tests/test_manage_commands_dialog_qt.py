from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import (
    QComboBox, QDialog, QLineEdit, QPlainTextEdit, QPushButton,
)

from worktree_manager.models import SavedCommand
from worktree_manager.ui.manage_commands_dialog import ManageCommandsDialog


def _vm(commands=None, repos=None, last_used="/repos/proj"):
    vm = MagicMock()
    vm.all_repos.return_value = repos or {"/repos/proj": MagicMock()}
    vm.get_last_used_repo.return_value = last_used
    vm.saved_commands.return_value = (
        [SavedCommand(name="build", command="make build"),
         SavedCommand(name="test", command="pytest")]
        if commands is None else commands
    )
    return vm


def _dlg(qtbot, vm=None):
    d = ManageCommandsDialog(parent=None, vm=vm or _vm())
    qtbot.addWidget(d)
    return d


def _buttons(d):
    return [b.text() for b in d.findChildren(QPushButton)]


def test_manage_commands_dialog_is_qdialog(qtbot):
    assert isinstance(_dlg(qtbot), QDialog)


def test_manage_commands_dialog_lists_saved_commands(qtbot):
    d = _dlg(qtbot)
    from PySide6.QtWidgets import QLabel
    all_text = " ".join(l.text() for l in d.findChildren(QLabel))
    assert "build" in all_text
    assert "test" in all_text


def test_manage_commands_dialog_has_add_command_button(qtbot):
    d = _dlg(qtbot)
    assert any("Add Command" in t for t in _buttons(d))


def test_manage_commands_dialog_has_done_button(qtbot):
    d = _dlg(qtbot)
    assert "Done" in _buttons(d)


def test_manage_commands_dialog_delete_calls_vm(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d._delete("build")
    vm.delete_command.assert_called_once_with("/repos/proj", "build")


def test_manage_commands_dialog_start_edit_swaps_row(qtbot):
    d = _dlg(qtbot)
    d._start_edit("build")
    assert d._editing_name == "build"
    assert d.findChild(QLineEdit) is not None
    assert d.findChild(QPlainTextEdit) is not None


def test_manage_commands_dialog_save_edit_same_name(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d._save_edit("build", "build", "make build -j")
    vm.save_command.assert_called_once_with("/repos/proj", "build", "make build -j")
    vm.delete_command.assert_not_called()


def test_manage_commands_dialog_save_edit_rename_deletes_old_first(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d._save_edit("build", "compile", "make build -j")
    vm.delete_command.assert_called_once_with("/repos/proj", "build")
    vm.save_command.assert_called_once_with("/repos/proj", "compile", "make build -j")


def test_manage_commands_dialog_save_edit_blank_name_is_noop(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    d._save_edit("build", "  ", "make build")
    vm.save_command.assert_not_called()


def test_manage_commands_dialog_cancel_edit_clears_editing_state(qtbot):
    d = _dlg(qtbot)
    d._start_edit("build")
    d._cancel_edit()
    assert d._editing_name is None


def test_manage_commands_dialog_repo_change_refreshes(qtbot):
    vm = _vm(repos={"/repos/proj": MagicMock(), "/repos/api": MagicMock()})
    d = _dlg(qtbot, vm=vm)
    combo = d.findChild(QComboBox)
    combo.setCurrentText("api")
    vm.set_last_used_repo.assert_called_with("/repos/api")


def test_manage_commands_dialog_add_command_opens_add_dialog(qtbot):
    d = _dlg(qtbot)
    with patch(
        "worktree_manager.ui.manage_commands_dialog.AddCommandDialog"
    ) as MockDlg:
        instance = MagicMock(spec=QDialog)
        MockDlg.return_value = instance
        d._open_add_command_dialog()
    MockDlg.assert_called_once()
    instance.exec.assert_called_once()


def test_manage_commands_dialog_empty_repo_shows_empty_label(qtbot):
    vm = _vm(commands=[])
    d = _dlg(qtbot, vm=vm)
    from PySide6.QtWidgets import QLabel
    all_text = " ".join(l.text() for l in d.findChildren(QLabel))
    assert "No commands saved" in all_text
