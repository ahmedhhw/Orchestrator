import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QPushButton

from worktree_manager.models import WorktreeModel
from worktree_manager.ui.delete_dialog import DeleteDialog


def _make_wt(branch="fix/auth", path="/r/proj-wt/fix-auth"):
    return WorktreeModel(
        path=path, branch=branch, is_main=False,
        last_commit_ts=int(time.time()), is_merged=False, is_stale=False,
    )


def test_delete_dialog_is_qdialog(qtbot):
    d = DeleteDialog(parent=None, wt=_make_wt(), on_delete=lambda *a: None)
    qtbot.addWidget(d)
    assert isinstance(d, QDialog)


def test_delete_dialog_shows_branch_and_path(qtbot):
    d = DeleteDialog(
        parent=None,
        wt=_make_wt(branch="feature/x", path="/repos/wt/feature-x"),
        on_delete=lambda *a: None,
    )
    qtbot.addWidget(d)
    texts = " ".join(l.text() for l in d.findChildren(QLabel))
    assert "feature/x" in texts
    assert "/repos/wt/feature-x" in texts


def test_delete_dialog_normal_branch_checkbox_enabled_and_checked(qtbot):
    d = DeleteDialog(parent=None, wt=_make_wt(),
                     on_delete=lambda *a: None, is_protected=False)
    qtbot.addWidget(d)
    cb = d.findChild(QCheckBox)
    assert cb.isEnabled()
    assert cb.isChecked()
    assert d._also_branch.get() is True


def test_delete_dialog_protected_branch_checkbox_disabled_and_unchecked(qtbot):
    d = DeleteDialog(parent=None, wt=_make_wt(),
                     on_delete=lambda *a: None, is_protected=True)
    qtbot.addWidget(d)
    cb = d.findChild(QCheckBox)
    assert not cb.isEnabled()
    assert not cb.isChecked()
    assert d._also_branch.get() is False
    assert "protected" in cb.text().lower()


def test_delete_dialog_cancel_does_not_call_on_delete(qtbot):
    calls = []
    d = DeleteDialog(parent=None, wt=_make_wt(),
                     on_delete=lambda *a: calls.append(a))
    qtbot.addWidget(d)
    cancel = next(b for b in d.findChildren(QPushButton) if b.text() == "Cancel")
    qtbot.mouseClick(cancel, Qt.LeftButton)
    assert calls == []


def test_delete_dialog_delete_calls_on_delete_with_checkbox_value(qtbot):
    calls = []
    wt = _make_wt()
    d = DeleteDialog(parent=None, wt=wt, on_delete=lambda *a: calls.append(a))
    qtbot.addWidget(d)
    d._also_branch.set(False)
    delete = next(b for b in d.findChildren(QPushButton) if b.text() == "Delete")
    qtbot.mouseClick(delete, Qt.LeftButton)
    assert len(calls) == 1
    assert calls[0] == (wt, False)


def test_delete_dialog_uncommitted_shows_warning_label(qtbot):
    d = DeleteDialog(
        parent=None, wt=_make_wt(),
        on_delete=lambda *a: None, has_uncommitted=True,
    )
    qtbot.addWidget(d)
    texts = " ".join(l.text() for l in d.findChildren(QLabel))
    assert "uncommitted" in texts.lower()


def test_delete_dialog_uncommitted_blocks_delete_with_messagebox(qtbot):
    calls = []
    d = DeleteDialog(parent=None, wt=_make_wt(),
                     on_delete=lambda *a: calls.append(a), has_uncommitted=True)
    qtbot.addWidget(d)
    delete = next(b for b in d.findChildren(QPushButton)
                  if b.text() in ("Delete", "Delete & Close"))
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_err:
        qtbot.mouseClick(delete, Qt.LeftButton)
    mock_err.assert_called_once()
    assert calls == []


def test_delete_dialog_live_window_shows_editor_warning_and_changes_button(qtbot):
    live = MagicMock()
    live.editor = "cursor"
    d = DeleteDialog(parent=None, wt=_make_wt(),
                     on_delete=lambda *a: None, live_window=live)
    qtbot.addWidget(d)
    texts = " ".join(l.text() for l in d.findChildren(QLabel))
    assert "Cursor" in texts
    btn_texts = [b.text() for b in d.findChildren(QPushButton)]
    assert "Delete & Close" in btn_texts
