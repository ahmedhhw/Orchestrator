from unittest.mock import MagicMock

from PySide6.QtWidgets import (
    QComboBox, QDialog, QLineEdit, QPlainTextEdit, QPushButton,
)

from worktree_manager.ui.add_command_dialog import AddCommandDialog


def _vm(repos=None, last_used=None):
    vm = MagicMock()
    vm.all_repos.return_value = repos or {
        "/repos/proj": MagicMock(), "/repos/api": MagicMock(),
    }
    vm.get_last_used_repo.return_value = last_used
    return vm


def _dlg(qtbot, vm=None, initial_repo=None, on_saved=None):
    d = AddCommandDialog(
        parent=None, vm=vm or _vm(),
        initial_repo=initial_repo, on_saved=on_saved,
    )
    qtbot.addWidget(d)
    return d


def test_add_command_dialog_is_qdialog(qtbot):
    assert isinstance(_dlg(qtbot), QDialog)


def test_add_command_dialog_defaults_repo_to_initial_repo(qtbot):
    d = _dlg(qtbot, initial_repo="/repos/api")
    combo = d.findChild(QComboBox)
    assert combo.currentText() == "api"


def test_add_command_dialog_defaults_repo_to_last_used_when_no_initial(qtbot):
    vm = _vm(last_used="/repos/api")
    d = _dlg(qtbot, vm=vm)
    combo = d.findChild(QComboBox)
    assert combo.currentText() == "api"


def test_add_command_dialog_defaults_repo_to_first_when_no_pref(qtbot):
    d = _dlg(qtbot)
    combo = d.findChild(QComboBox)
    assert combo.currentText() in ("proj", "api")


def test_add_command_dialog_cancel_does_not_save(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm)
    cancel = next(b for b in d.findChildren(QPushButton) if b.text() == "Cancel")
    cancel.click()
    vm.save_command.assert_not_called()


def test_add_command_dialog_save_calls_vm_with_values(qtbot):
    vm = _vm()
    saved = []
    d = _dlg(qtbot, vm=vm, initial_repo="/repos/api",
             on_saved=lambda: saved.append("ok"))
    d.findChild(QLineEdit).setText("build")
    d.findChild(QPlainTextEdit).setPlainText("make build")
    save = next(b for b in d.findChildren(QPushButton) if b.text() == "Save")
    save.click()
    vm.save_command.assert_called_once_with("/repos/api", "build", "make build", startup_pattern=None)
    vm.set_last_used_repo.assert_called_once_with("/repos/api")
    assert saved == ["ok"]


def test_add_command_dialog_save_with_blank_name_does_nothing(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm, initial_repo="/repos/api")
    d.findChild(QPlainTextEdit).setPlainText("make build")
    save = next(b for b in d.findChildren(QPushButton) if b.text() == "Save")
    save.click()
    vm.save_command.assert_not_called()


def test_add_command_dialog_save_with_blank_command_does_nothing(qtbot):
    vm = _vm()
    d = _dlg(qtbot, vm=vm, initial_repo="/repos/api")
    d.findChild(QLineEdit).setText("build")
    save = next(b for b in d.findChildren(QPushButton) if b.text() == "Save")
    save.click()
    vm.save_command.assert_not_called()
