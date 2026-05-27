import time
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView


def _make_vm():
    now = int(time.time())
    vm = MagicMock(spec=MainWindowViewModel)
    vm.load_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
    ]
    vm.list_branches_with_checkout_status.return_value = [
        ("main", True), ("fix/auth", True), ("hotfix/2.1", False),
    ]
    return vm


def _make_view(qtbot, vm=None, on_cleanup=None, on_new=None):
    view = PerRepoWorktreesView(
        vm=vm or _make_vm(),
        repo_name="proj",
        on_cleanup=on_cleanup or (lambda: None),
        on_new=on_new or (lambda: None),
    )
    qtbot.addWidget(view)
    return view


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def _buttons(widget):
    return widget.findChildren(QPushButton)


def _button_texts(widget):
    return [b.text() for b in _buttons(widget)]


def test_header_shows_worktrees_and_repo_name(qtbot):
    view = _make_view(qtbot)
    texts = _label_texts(view)
    assert any("Worktrees" in t and "proj" in t for t in texts)


def test_header_does_not_say_git_worktree_manager(qtbot):
    view = _make_view(qtbot)
    texts = _label_texts(view)
    assert not any("Git Worktree Manager" in t for t in texts)


def test_no_settings_button(qtbot):
    view = _make_view(qtbot)
    assert not any("⚙" in t for t in _button_texts(view))


def test_has_cleanup_and_new_buttons(qtbot):
    view = _make_view(qtbot)
    texts = _button_texts(view)
    assert any("🧹" in t for t in texts)
    assert any("New" in t for t in texts)


def test_lists_worktrees(qtbot):
    view = _make_view(qtbot)
    texts = _label_texts(view)
    assert any("fix-auth" in t for t in texts)
    assert any("(main)" in t for t in texts)


def test_branch_dropdowns_present_for_each_worktree(qtbot):
    view = _make_view(qtbot)
    combos = view.findChildren(QComboBox)
    assert len(combos) == 2


def test_branch_dropdown_lists_all_branches(qtbot):
    view = _make_view(qtbot)
    combo = view.findChildren(QComboBox)[0]
    values = [combo.itemText(i) for i in range(combo.count())]
    assert "main" in values
    assert "fix/auth" in values
    assert "hotfix/2.1" in values


def test_cleanup_button_invokes_callback(qtbot):
    triggered: list = []
    view = _make_view(qtbot, on_cleanup=lambda: triggered.append(1))
    btn = next(b for b in _buttons(view) if "🧹" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == [1]


def test_new_button_invokes_callback(qtbot):
    triggered: list = []
    view = _make_view(qtbot, on_new=lambda: triggered.append(1))
    btn = next(b for b in _buttons(view) if "New" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert triggered == [1]


def test_switch_branch_calls_vm(qtbot):
    vm = _make_vm()
    view = _make_view(qtbot, vm=vm)
    combo = view.findChildren(QComboBox)[0]
    combo.setCurrentText("hotfix/2.1")
    vm.switch_branch.assert_called()


def test_delete_button_absent_for_main_worktree(qtbot):
    view = _make_view(qtbot)
    del_buttons = [b for b in _buttons(view) if b.text() == "✕"]
    assert len(del_buttons) == 1


def test_show_toast_displays_message(qtbot):
    view = _make_view(qtbot)
    view.show_toast("hello toast")
    labels = [lbl for lbl in view.findChildren(QLabel) if "hello toast" in lbl.text()]
    assert labels
    assert not labels[0].isHidden()
