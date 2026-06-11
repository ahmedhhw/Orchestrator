import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView


def _make_vm(worktrees=None, branch_status=None):
    now = int(time.time())
    if worktrees is None:
        worktrees = [
            WorktreeModel("/repos/proj", "main", True, now, False, False),
            WorktreeModel("/repos/proj-wt/fix-auth", "fix/auth", False, now - 3600, False, False),
        ]
    if branch_status is None:
        branch_status = [("main", True), ("fix/auth", True), ("hotfix/2.1", False)]
    vm = MagicMock(spec=MainWindowViewModel)
    vm.load_worktree_view_data.return_value = {
        "worktrees": worktrees,
        "branch_status": branch_status,
    }
    vm.is_protected_branch.return_value = False
    return vm


def _make_window(qtbot, vm=None, on_cleanup=None, on_new=None):
    win = PerRepoWorktreesView(
        vm=vm or _make_vm(),
        repo_name="proj",
        on_cleanup=on_cleanup or (lambda: None),
        on_new=on_new or (lambda: None),
    )
    qtbot.addWidget(win)
    win.show()
    qtbot.waitUntil(lambda: win._loading is False, timeout=3000)
    return win


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def _buttons(widget):
    return widget.findChildren(QPushButton)


def test_main_window_header_shows_repo_name(qtbot):
    win = _make_window(qtbot)
    assert any("proj" in t for t in _label_texts(win))


def test_main_window_has_new_and_cleanup_buttons(qtbot):
    win = _make_window(qtbot)
    btn_texts = [b.text() for b in _buttons(win)]
    assert any("New" in t for t in btn_texts)
    assert any("🧹" in t for t in btn_texts)


def test_main_window_lists_non_main_worktree_folder_names(qtbot):
    win = _make_window(qtbot)
    texts = _label_texts(win)
    assert any("fix-auth" in t for t in texts)
    assert any("(main)" in t for t in texts)


def test_main_window_shows_branch_dropdown_per_worktree(qtbot):
    win = _make_window(qtbot)
    combos = win.findChildren(QComboBox)
    assert len(combos) == 2


def test_main_window_branch_dropdown_lists_all_branches(qtbot):
    win = _make_window(qtbot)
    combo = win.findChildren(QComboBox)[0]
    values = [combo.itemText(i) for i in range(combo.count())]
    assert "main" in values
    assert "fix/auth" in values
    assert "hotfix/2.1" in values


def test_main_window_switch_branch_calls_vm(qtbot):
    vm = _make_vm()
    win = _make_window(qtbot, vm=vm)
    win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    vm.switch_branch.assert_called_once_with("/repos/proj-wt/fix-auth", "hotfix/2.1")


def test_main_window_switch_branch_shows_error_on_uncommitted(qtbot):
    vm = _make_vm()
    vm.switch_branch.side_effect = ValueError("uncommitted changes")
    win = _make_window(qtbot, vm=vm)
    with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_err:
        result = win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    mock_err.assert_called_once()
    assert result is False


def test_main_window_switch_branch_refreshes_on_success(qtbot):
    vm = _make_vm()
    win = _make_window(qtbot, vm=vm)
    initial = vm.load_worktree_view_data.call_count
    win._switch_branch("/repos/proj-wt/fix-auth", "hotfix/2.1")
    assert vm.load_worktree_view_data.call_count > initial


def test_main_window_new_button_invokes_callback(qtbot):
    called: list = []
    win = _make_window(qtbot, on_new=lambda: called.append("new"))
    btn = next(b for b in _buttons(win) if "New" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert called == ["new"]


def test_main_window_cleanup_button_invokes_callback(qtbot):
    called: list = []
    win = _make_window(qtbot, on_cleanup=lambda: called.append("cleanup"))
    btn = next(b for b in _buttons(win) if "🧹" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert called == ["cleanup"]


def test_main_window_stale_worktree_shows_warning(qtbot):
    vm = _make_vm(
        worktrees=[WorktreeModel("/repos/proj-wt/old", "old", False, 0, False, True)],
    )
    win = _make_window(qtbot, vm=vm)
    texts = _label_texts(win)
    assert any("stale" in t for t in texts)
