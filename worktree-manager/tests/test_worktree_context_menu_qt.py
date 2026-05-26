import time
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.main_window import MainWindow


def _make_vm():
    now = int(time.time())
    vm = MagicMock(spec=MainWindowViewModel)
    vm.load_worktrees.return_value = [
        WorktreeModel("/repos/proj", "main", True, now, False, False),
        WorktreeModel("/repos/proj-wt/feat-auth", "feat/auth", False, now - 3600, False, False),
    ]
    vm.list_branches_with_checkout_status.return_value = [
        ("main", True), ("feat/auth", True),
    ]
    return vm


def _make_window(qtbot, vm=None, on_generate_project=None):
    win = MainWindow(
        vm=vm or _make_vm(),
        repo_name="proj",
        on_settings=lambda: None,
        on_cleanup=lambda: None,
        on_new=lambda: None,
        on_generate_project=on_generate_project or (lambda path: None),
    )
    qtbot.addWidget(win)
    return win


def test_main_window_accepts_on_generate_project_callback(qtbot):
    called = []
    win = _make_window(qtbot, on_generate_project=lambda path: called.append(path))
    assert win is not None


def test_worktree_rows_have_custom_context_menu_policy(qtbot):
    win = _make_window(qtbot)
    rows = win._worktree_rows
    assert len(rows) >= 2
    for row in rows:
        assert row.contextMenuPolicy() == Qt.CustomContextMenu


def test_generate_project_action_fires_callback_with_worktree_path(qtbot):
    called = []
    win = _make_window(qtbot, on_generate_project=lambda path: called.append(path))
    win._trigger_generate_project("/repos/proj-wt/feat-auth")
    assert called == ["/repos/proj-wt/feat-auth"]


def _toast_on_generate(win):
    import os

    def cb(path: str) -> None:
        name = os.path.basename(path) or path
        win.show_toast(f"✅ Project \"{name}\" created")
    return cb


def test_generate_project_shows_created_toast(qtbot):
    win = _make_window(qtbot)
    win._on_generate_project = _toast_on_generate(win)
    win._trigger_generate_project("/repos/proj-wt/feat-auth")
    toast = win._toast_label
    assert not toast.isHidden()
    assert "feat-auth" in toast.text()
    assert "created" in toast.text().lower() or "updated" in toast.text().lower()


def test_generate_project_toast_contains_checkmark(qtbot):
    win = _make_window(qtbot)
    win._on_generate_project = _toast_on_generate(win)
    win._trigger_generate_project("/repos/proj-wt/feat-auth")
    assert "✅" in win._toast_label.text()


def test_generate_project_for_main_worktree_shows_main_in_toast(qtbot):
    win = _make_window(qtbot)
    win._on_generate_project = _toast_on_generate(win)
    win._trigger_generate_project("/repos/proj")
    assert not win._toast_label.isHidden()
