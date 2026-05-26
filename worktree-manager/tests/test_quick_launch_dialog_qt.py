from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QPushButton

from worktree_manager.ui.quick_launch_dialog import QuickLaunchDialog


def _make_dialog(qtbot, worktree_path="/repos/proj-wt/feat-auth", on_run=None):
    dlg = QuickLaunchDialog(
        parent=None,
        worktree_path=worktree_path,
        on_run=on_run or (lambda cmd: None),
    )
    qtbot.addWidget(dlg)
    return dlg


def test_dialog_shows_worktree_path(qtbot):
    dlg = _make_dialog(qtbot, worktree_path="/repos/proj-wt/feat-auth")
    labels = dlg.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]
    assert any("feat-auth" in t for t in texts)


def test_dialog_has_command_input(qtbot):
    dlg = _make_dialog(qtbot)
    inputs = dlg.findChildren(QLineEdit)
    assert len(inputs) >= 1


def test_run_button_calls_on_run_with_command(qtbot):
    called = []
    dlg = _make_dialog(qtbot, on_run=lambda cmd: called.append(cmd))
    dlg._cmd_input.setText("echo hello")
    dlg.trigger_run()
    assert called == ["echo hello"]


def test_run_button_does_nothing_when_command_empty(qtbot):
    called = []
    dlg = _make_dialog(qtbot, on_run=lambda cmd: called.append(cmd))
    dlg._cmd_input.setText("   ")
    dlg.trigger_run()
    assert called == []


def test_cancel_closes_dialog(qtbot):
    dlg = _make_dialog(qtbot)
    dlg.show()
    dlg.reject()
    assert not dlg.isVisible()


def test_run_closes_dialog(qtbot):
    dlg = _make_dialog(qtbot, on_run=lambda cmd: None)
    dlg.show()
    dlg._cmd_input.setText("ls")
    dlg.trigger_run()
    assert not dlg.isVisible()
