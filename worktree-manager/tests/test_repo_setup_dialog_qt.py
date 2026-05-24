from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton

from worktree_manager.setup_settings_vm import RepoSetupViewModel
from worktree_manager.ui.repo_setup_dialog import RepoSetupDialog


def _make_vm(default_path="/repos/proj-worktrees"):
    vm = MagicMock(spec=RepoSetupViewModel)
    vm.default_storage_path.return_value = default_path
    return vm


def test_repo_setup_dialog_is_qdialog(qtbot):
    vm = _make_vm()
    d = RepoSetupDialog(parent=None, vm=vm, on_confirm=lambda: None)
    qtbot.addWidget(d)
    assert isinstance(d, QDialog)


def test_repo_setup_dialog_prefills_default_path(qtbot):
    vm = _make_vm(default_path="/repos/myrepo-worktrees")
    d = RepoSetupDialog(parent=None, vm=vm, on_confirm=lambda: None)
    qtbot.addWidget(d)
    entry = d.findChild(QLineEdit)
    assert entry.text() == "/repos/myrepo-worktrees"


def test_repo_setup_dialog_has_cancel_and_confirm_buttons(qtbot):
    vm = _make_vm()
    d = RepoSetupDialog(parent=None, vm=vm, on_confirm=lambda: None)
    qtbot.addWidget(d)
    btn_texts = [b.text() for b in d.findChildren(QPushButton)]
    assert "Cancel" in btn_texts
    assert "Confirm" in btn_texts


def test_repo_setup_dialog_cancel_closes_without_calling_vm(qtbot):
    vm = _make_vm()
    called = []
    d = RepoSetupDialog(parent=None, vm=vm, on_confirm=lambda: called.append("ok"))
    qtbot.addWidget(d)
    cancel = next(b for b in d.findChildren(QPushButton) if b.text() == "Cancel")
    qtbot.mouseClick(cancel, Qt.LeftButton)
    vm.confirm.assert_not_called()
    assert called == []


def test_repo_setup_dialog_confirm_calls_vm_with_entry_text(qtbot):
    vm = _make_vm()
    called = []
    d = RepoSetupDialog(parent=None, vm=vm, on_confirm=lambda: called.append("ok"))
    qtbot.addWidget(d)
    entry = d.findChild(QLineEdit)
    entry.setText("/somewhere/else")
    confirm = next(b for b in d.findChildren(QPushButton) if b.text() == "Confirm")
    qtbot.mouseClick(confirm, Qt.LeftButton)
    vm.confirm.assert_called_once()
    kwargs = vm.confirm.call_args.kwargs
    assert kwargs["storage_path"] == "/somewhere/else"
    assert callable(kwargs["callback"])


def test_repo_setup_dialog_browse_button_updates_entry(qtbot):
    vm = _make_vm()
    d = RepoSetupDialog(parent=None, vm=vm, on_confirm=lambda: None)
    qtbot.addWidget(d)
    browse = next(b for b in d.findChildren(QPushButton) if b.text() == "Browse")
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
               return_value="/picked/path"):
        qtbot.mouseClick(browse, Qt.LeftButton)
    entry = d.findChild(QLineEdit)
    assert entry.text() == "/picked/path"


def test_repo_setup_dialog_browse_cancel_leaves_entry_unchanged(qtbot):
    vm = _make_vm(default_path="/orig")
    d = RepoSetupDialog(parent=None, vm=vm, on_confirm=lambda: None)
    qtbot.addWidget(d)
    browse = next(b for b in d.findChildren(QPushButton) if b.text() == "Browse")
    with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=""):
        qtbot.mouseClick(browse, Qt.LeftButton)
    entry = d.findChild(QLineEdit)
    assert entry.text() == "/orig"
