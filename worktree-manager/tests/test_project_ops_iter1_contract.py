"""Behavioral contract — Iteration 1: Project Operations dialog.

Copy buttons (New + Existing panels) + create-worktree loading indicator.
Run: python3.14 -m pytest tests/test_project_ops_iter1_contract.py
"""
import threading
from unittest.mock import MagicMock

from PySide6.QtWidgets import QLabel, QLineEdit, QProgressBar, QPushButton, QRadioButton

from worktree_manager.workspace_projects_vm import WorktreeStatus
from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog


# ── helpers ───────────────────────────────────────────────────────────────────

def _status(path, branch="main", is_main=False, dirty=False):
    return WorktreeStatus(path=path, branch=branch, is_main=is_main,
                          has_uncommitted=dirty)


def _vm(create_result=None, branches=None):
    vm = MagicMock()
    vm.list_worktrees_with_dirty.return_value = []
    vm.list_branches_for_worktree.return_value = branches or ["main", "fix/auth"]
    vm.create_worktree_for_project.return_value = (
        create_result or _status("/r/new", "fix/auth")
    )
    return vm


def _dlg(qtbot, vm=None, repos=None):
    d = ProjectOperationsDialog(
        parent=None,
        vm=vm or _vm(),
        repos=repos or {"/repos/proj": MagicMock()},
        on_create=lambda name, entries: None,
    )
    qtbot.addWidget(d)
    return d


def _open_new_branch_panel(d):
    btn = next(b for b in d.findChildren(QPushButton)
               if "Create new worktree" in b.text())
    btn.click()
    d._new_branch_radio.setChecked(True)


def _open_existing_panel(d):
    btn = next(b for b in d.findChildren(QPushButton)
               if "Create new worktree" in b.text())
    btn.click()
    d._existing_branch_radio.setChecked(True)


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


# ── 1 · Copy buttons — New branch panel ──────────────────────────────────────

def test_new_branch_panel_has_copy_branch_to_wt_button(qtbot):
    """'← copy from branch' button is present in the New-branch panel."""
    d = _dlg(qtbot)
    _open_new_branch_panel(d)
    assert any("copy from branch" in t.lower() for t in _button_texts(d))


def test_new_branch_panel_has_copy_wt_to_branch_button(qtbot):
    """'← copy from worktree' button is present in the New-branch panel."""
    d = _dlg(qtbot)
    _open_new_branch_panel(d)
    assert any("copy from worktree" in t.lower() for t in _button_texts(d))


def test_copy_branch_to_wt_fills_wt_name_with_slash_converted(qtbot):
    """'← copy from branch' fills the worktree-name field, replacing / with -."""
    d = _dlg(qtbot)
    _open_new_branch_panel(d)
    d._new_branch_le.setText("fix/auth")
    btn = next(b for b in d.findChildren(QPushButton)
               if "copy from branch" in b.text().lower())
    btn.click()
    assert d._new_wt_name_le.text() == "fix-auth"


def test_copy_wt_to_branch_fills_branch_with_first_dash_converted(qtbot):
    """'← copy from worktree' fills the branch-name field, replacing first - with /."""
    d = _dlg(qtbot)
    _open_new_branch_panel(d)
    d._new_wt_name_le.setText("fix-auth")
    btn = next(b for b in d.findChildren(QPushButton)
               if "copy from worktree" in b.text().lower())
    btn.click()
    assert d._new_branch_le.text() == "fix/auth"


# ── 2 · Copy button — Existing branch panel ──────────────────────────────────

def test_existing_branch_panel_has_copy_from_branch_button(qtbot):
    """'← copy from branch' button is present in the Existing-branch panel."""
    d = _dlg(qtbot)
    _open_existing_panel(d)
    assert any("copy from branch" in t.lower() for t in _button_texts(d))


def test_existing_copy_fills_wt_name_from_dropdown(qtbot):
    """'← copy from branch' in Existing panel fills wt-name from the branch dropdown."""
    vm = _vm(branches=["main", "fix/auth"])
    vm.list_worktrees_with_dirty.return_value = [_status("/r/main", "main", is_main=True)]
    d = _dlg(qtbot, vm=vm)
    _open_existing_panel(d)
    d._existing_branch_combo.setCurrentText("fix/auth")
    # scope to the existing-branch frame to avoid hitting the New-branch copy button
    btn = next(b for b in d._existing_branch_frame.findChildren(QPushButton)
               if "copy from branch" in b.text().lower())
    btn.click()
    assert d._existing_wt_name_le.text() == "fix-auth"


# ── 3 · Create-worktree loading indicator ────────────────────────────────────

def test_create_wt_shows_progress_bar_while_running(qtbot):
    """An indeterminate progress bar appears in the panel while create is in flight."""
    gate = threading.Event()

    def slow_create(repo_path, spec):
        gate.wait(timeout=3)
        return _status("/r/new", "fix/auth")

    vm = _vm()
    vm.create_worktree_for_project.side_effect = slow_create
    d = _dlg(qtbot, vm=vm)
    _open_new_branch_panel(d)
    d._new_wt_name_le.setText("fix-auth")
    d._new_branch_le.setText("fix/auth")

    create_btn = next(b for b in d.findChildren(QPushButton)
                      if b.text() == "Create + Add")
    create_btn.click()

    assert d.findChild(QProgressBar) is not None
    gate.set()
    qtbot.waitUntil(lambda: not d._create_wt_panel.isVisibleTo(d), timeout=3000)


def test_create_wt_disables_create_button_while_running(qtbot):
    """'Create + Add' is disabled while creation is in flight."""
    gate = threading.Event()

    def slow_create(repo_path, spec):
        gate.wait(timeout=3)
        return _status("/r/new", "fix/auth")

    vm = _vm()
    vm.create_worktree_for_project.side_effect = slow_create
    d = _dlg(qtbot, vm=vm)
    _open_new_branch_panel(d)
    d._new_wt_name_le.setText("fix-auth")
    d._new_branch_le.setText("fix/auth")

    create_btn = next(b for b in d.findChildren(QPushButton)
                      if b.text() == "Create + Add")
    create_btn.click()

    assert not create_btn.isEnabled()
    gate.set()
    qtbot.waitUntil(lambda: not d._create_wt_panel.isVisibleTo(d), timeout=3000)


def test_create_wt_panel_closes_on_success(qtbot):
    """After successful creation, the create-worktree panel is hidden."""
    d = _dlg(qtbot)
    _open_new_branch_panel(d)
    d._new_wt_name_le.setText("fix-auth")
    d._new_branch_le.setText("fix/auth")

    create_btn = next(b for b in d.findChildren(QPushButton)
                      if b.text() == "Create + Add")
    create_btn.click()
    qtbot.waitUntil(lambda: not d._create_wt_panel.isVisibleTo(d), timeout=3000)


def test_create_wt_adds_entry_on_success(qtbot):
    """After successful creation, the new worktree path appears in entries."""
    d = _dlg(qtbot)
    _open_new_branch_panel(d)
    d._new_wt_name_le.setText("fix-auth")
    d._new_branch_le.setText("fix/auth")

    create_btn = next(b for b in d.findChildren(QPushButton)
                      if b.text() == "Create + Add")
    create_btn.click()
    qtbot.waitUntil(lambda: "/r/new" in d.get_entries(), timeout=3000)


def test_create_wt_shows_error_on_failure(qtbot):
    """On failure, the inline error label shows the error text; panel stays open."""
    vm = _vm()
    err = Exception("branch already exists")
    err.stderr = "fatal: branch already exists"
    vm.create_worktree_for_project.side_effect = err
    d = _dlg(qtbot, vm=vm)
    _open_new_branch_panel(d)
    d._new_wt_name_le.setText("fix-auth")
    d._new_branch_le.setText("fix/auth")

    create_btn = next(b for b in d.findChildren(QPushButton)
                      if b.text() == "Create + Add")
    create_btn.click()
    qtbot.waitUntil(lambda: bool(d._create_wt_error.text()), timeout=3000)
    assert "already exists" in d._create_wt_error.text().lower()
    assert d._create_wt_panel.isVisibleTo(d)


def test_create_wt_re_enables_create_button_after_failure(qtbot):
    """After a failure, 'Create + Add' is re-enabled so the user can retry."""
    vm = _vm()
    vm.create_worktree_for_project.side_effect = Exception("boom")
    d = _dlg(qtbot, vm=vm)
    _open_new_branch_panel(d)
    d._new_wt_name_le.setText("fix-auth")
    d._new_branch_le.setText("fix/auth")

    create_btn = next(b for b in d.findChildren(QPushButton)
                      if b.text() == "Create + Add")
    create_btn.click()
    qtbot.waitUntil(lambda: create_btn.isEnabled(), timeout=3000)
