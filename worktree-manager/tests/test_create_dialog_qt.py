from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QRadioButton

from worktree_manager.ui.create_dialog import CreateDialog


def _make_dialog(qtbot, branches=None, existing_branches=None, on_create=None):
    d = CreateDialog(
        parent=None,
        branches=branches or ["main"],
        existing_branches=existing_branches or [],
        on_create=on_create or (lambda *a: None),
    )
    qtbot.addWidget(d)
    return d


def test_create_dialog_is_qdialog(qtbot):
    d = _make_dialog(qtbot)
    assert isinstance(d, QDialog)


def test_create_dialog_starts_in_new_branch_mode(qtbot):
    d = _make_dialog(qtbot)
    assert d._mode_var.get() == "new"


def test_create_dialog_has_two_mode_radio_buttons(qtbot):
    d = _make_dialog(qtbot)
    labels = [r.text() for r in d.findChildren(QRadioButton)]
    assert "New branch" in labels
    assert "Existing branch" in labels


def test_create_dialog_cancel_does_not_call_on_create(qtbot):
    calls = []
    d = _make_dialog(qtbot, on_create=lambda *a: calls.append(a))
    cancel = next(b for b in d.findChildren(QPushButton) if b.text() == "Cancel")
    qtbot.mouseClick(cancel, Qt.LeftButton)
    assert calls == []


def test_create_dialog_new_mode_create_calls_callback_with_correct_args(qtbot):
    calls = []
    d = _make_dialog(qtbot, branches=["main", "develop"],
                     on_create=lambda *a: calls.append(a))
    d._mode_var.set("new")
    d._on_mode_change()
    d._branch_entry.insert(0, "fix/login")
    d._base_var.set("main")
    d._wt_name_entry.clear()
    d._wt_name_entry.insert(0, "fix-login")
    d._create()
    assert len(calls) == 1
    branch, base, is_existing, wt_name = calls[0]
    assert (branch, base, is_existing, wt_name) == ("fix/login", "main", False, "fix-login")


def test_create_dialog_new_mode_empty_branch_does_not_call_callback(qtbot):
    calls = []
    d = _make_dialog(qtbot, on_create=lambda *a: calls.append(a))
    d._mode_var.set("new")
    d._on_mode_change()
    d._create()
    assert calls == []


def test_create_dialog_existing_mode_calls_callback_with_correct_args(qtbot):
    calls = []
    d = _make_dialog(qtbot,
                     existing_branches=["fix/auth", "chore/deps"],
                     on_create=lambda *a: calls.append(a))
    d._mode_var.set("existing")
    d._on_mode_change()
    d._existing_var.set("fix/auth")
    d._existing_wt_name_entry.clear()
    d._existing_wt_name_entry.insert(0, "auth-wt")
    d._create()
    assert len(calls) == 1
    branch, base, is_existing, wt_name = calls[0]
    assert (branch, base, is_existing, wt_name) == ("fix/auth", None, True, "auth-wt")


def test_create_dialog_copy_branch_to_wt_name(qtbot):
    d = _make_dialog(qtbot)
    d._mode_var.set("new")
    d._on_mode_change()
    d._branch_entry.clear()
    d._branch_entry.insert(0, "fix/my-login")
    d._copy_branch_to_wt()
    assert d._wt_name_entry.get() == "fix-my-login"


def test_create_dialog_copy_wt_to_branch_name(qtbot):
    d = _make_dialog(qtbot)
    d._mode_var.set("new")
    d._on_mode_change()
    d._wt_name_entry.clear()
    d._wt_name_entry.insert(0, "fix-my-login")
    d._copy_wt_to_branch()
    assert d._branch_entry.get() == "fix/my-login"


def test_create_dialog_existing_copy_branch_fills_wt_name(qtbot):
    d = _make_dialog(qtbot, existing_branches=["fix/auth", "chore/deps"])
    d._mode_var.set("existing")
    d._on_mode_change()
    d._existing_var.set("fix/auth")
    d._copy_existing_branch_to_wt()
    assert d._existing_wt_name_entry.get() == "fix-auth"


def test_create_dialog_new_mode_passes_none_wt_name_when_empty(qtbot):
    calls = []
    d = _make_dialog(qtbot, on_create=lambda *a: calls.append(a))
    d._mode_var.set("new")
    d._on_mode_change()
    d._branch_entry.insert(0, "fix/x")
    d._wt_name_entry.clear()
    d._create()
    branch, base, is_existing, wt_name = calls[0]
    assert wt_name is None


def test_create_dialog_existing_mode_with_no_branches_does_not_call_callback(qtbot):
    calls = []
    d = _make_dialog(qtbot, existing_branches=[],
                     on_create=lambda *a: calls.append(a))
    d._mode_var.set("existing")
    d._on_mode_change()
    d._create()
    assert calls == []


def test_create_dialog_shows_only_new_widgets_in_new_mode(qtbot):
    d = _make_dialog(qtbot, existing_branches=["fix/auth"])
    d._mode_var.set("new")
    d._on_mode_change()
    assert d._new_frame.isVisibleTo(d)
    assert not d._existing_frame.isVisibleTo(d)


def test_create_dialog_shows_only_existing_widgets_in_existing_mode(qtbot):
    d = _make_dialog(qtbot, existing_branches=["fix/auth"])
    d._mode_var.set("existing")
    d._on_mode_change()
    assert d._existing_frame.isVisibleTo(d)
    assert not d._new_frame.isVisibleTo(d)
