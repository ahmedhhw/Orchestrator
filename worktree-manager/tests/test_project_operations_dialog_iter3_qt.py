"""Tests for ProjectOperationsDialog Iteration 3: dirty markers + inline create-worktree panel."""
from unittest.mock import MagicMock, patch
import subprocess

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QRadioButton, QLineEdit, QComboBox

from worktree_manager.models import WorktreeModel
from worktree_manager.workspace_projects_vm import WorktreeStatus
from worktree_manager.ui.project_operations_dialog import ProjectOperationsDialog


def _status(path, branch="main", is_main=True, dirty=False):
    return WorktreeStatus(path=path, branch=branch, is_main=is_main, has_uncommitted=dirty)


def _wt(path, branch="main", is_main=True):
    return WorktreeModel(
        path=path, branch=branch, is_main=is_main,
        last_commit_ts=0, is_merged=False, is_stale=False,
    )


def _vm(statuses=None, worktrees=None, branches=None):
    vm = MagicMock()
    vm.list_worktrees_with_dirty.return_value = statuses or []
    vm.list_worktrees_for_repo.return_value = worktrees or []
    vm.list_branches_for_worktree.return_value = branches or ["main", "feature/x"]
    vm.create_worktree_for_project.return_value = _status("/r/new", "fix/auth", is_main=False)
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


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def _button_texts(widget):
    return [b.text() for b in widget.findChildren(QPushButton)]


# ── dirty markers in worktree picker ─────────────────────────────────────────

def test_dirty_marker_shown_for_dirty_worktree_in_picker(qtbot):
    statuses = [
        _status("/r/main", "main", is_main=True, dirty=False),
        _status("/r/feat", "feature/x", is_main=False, dirty=True),
    ]
    d = _dlg(qtbot, vm=_vm(statuses=statuses))
    texts = _label_texts(d)
    assert any("⚠" in t for t in texts), f"Expected dirty marker in labels: {texts}"


def test_dirty_marker_not_shown_for_clean_worktree(qtbot):
    statuses = [_status("/r/main", "main", is_main=True, dirty=False)]
    d = _dlg(qtbot, vm=_vm(statuses=statuses))
    # There should be no dirty warning labels for the clean worktree row
    dirty_labels = [lbl for lbl in d.findChildren(QLabel) if "⚠" in lbl.text() and "dirty" in lbl.text().lower()]
    # Main label or entry warn may still be present; we want no per-row dirty label for clean wt
    # Just check that the dirty worktree labels match only dirty ones
    assert dirty_labels == [] or all("dirty" not in lbl.text().lower() or "entries" in lbl.text().lower() for lbl in dirty_labels)


def test_two_dirty_worktrees_show_two_markers(qtbot):
    statuses = [
        _status("/r/a", "main", dirty=True),
        _status("/r/b", "feature/x", is_main=False, dirty=True),
    ]
    d = _dlg(qtbot, vm=_vm(statuses=statuses))
    dirty_row_labels = [lbl for lbl in d.findChildren(QLabel)
                        if "⚠" in lbl.text() and "dirty" in lbl.text().lower()
                        and "entries" not in lbl.text().lower()]
    assert len(dirty_row_labels) >= 2


# ── dirty markers in entries list ────────────────────────────────────────────

def test_entries_dirty_footer_shown_when_entry_is_dirty(qtbot):
    statuses = [_status("/r/feat", "feature/x", is_main=False, dirty=True)]
    d = _dlg(qtbot, vm=_vm(statuses=statuses))
    d.trigger_add_entry("/r/feat")
    texts = _label_texts(d)
    assert any("uncommitted" in t.lower() for t in texts), f"Expected uncommitted warning in {texts}"


def test_entries_dirty_footer_not_shown_when_all_clean(qtbot):
    statuses = [_status("/r/main", "main", dirty=False)]
    d = _dlg(qtbot, vm=_vm(statuses=statuses))
    d.trigger_add_entry("/r/main")
    texts = _label_texts(d)
    assert not any("uncommitted" in t.lower() for t in texts)


def test_entries_dirty_marker_shown_per_dirty_entry(qtbot):
    statuses = [_status("/r/feat", "feature/x", is_main=False, dirty=True)]
    d = _dlg(qtbot, vm=_vm(statuses=statuses))
    d.trigger_add_entry("/r/feat")
    # There should be a ⚠ marker somewhere in the entries area
    texts = _label_texts(d)
    assert any("⚠" in t for t in texts)


def test_entries_dirty_count_updates_correctly(qtbot):
    statuses = [
        _status("/r/a", dirty=True),
        _status("/r/b", "feature/x", is_main=False, dirty=True),
    ]
    d = _dlg(qtbot, vm=_vm(statuses=statuses))
    d.trigger_add_entry("/r/a")
    d.trigger_add_entry("/r/b")
    texts = _label_texts(d)
    assert any("2" in t and "uncommitted" in t.lower() for t in texts)


# ── [+ Create new worktree] button present ───────────────────────────────────

def test_create_worktree_button_present(qtbot):
    d = _dlg(qtbot)
    btns = _button_texts(d)
    assert any("Create new worktree" in t for t in btns), f"Expected 'Create new worktree' button in {btns}"


def test_create_worktree_inline_panel_hidden_by_default(qtbot):
    d = _dlg(qtbot)
    assert not d._create_wt_panel.isVisibleTo(d)


def test_create_worktree_button_toggles_panel_open(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Create new worktree" in b.text())
    btn.click()
    assert d._create_wt_panel.isVisibleTo(d)


def test_create_worktree_panel_has_new_branch_radio(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Create new worktree" in b.text())
    btn.click()
    radios = d._create_wt_panel.findChildren(QRadioButton)
    assert any("new" in r.text().lower() for r in radios)


def test_create_worktree_panel_has_existing_branch_radio(qtbot):
    d = _dlg(qtbot)
    btn = next(b for b in d.findChildren(QPushButton) if "Create new worktree" in b.text())
    btn.click()
    radios = d._create_wt_panel.findChildren(QRadioButton)
    assert any("existing" in r.text().lower() for r in radios)


def test_create_worktree_panel_cancel_collapses_panel(qtbot):
    d = _dlg(qtbot)
    toggle_btn = next(b for b in d.findChildren(QPushButton) if "Create new worktree" in b.text())
    toggle_btn.click()
    assert d._create_wt_panel.isVisibleTo(d)
    cancel_btn = next(
        b for b in d._create_wt_panel.findChildren(QPushButton) if b.text() == "Cancel"
    )
    cancel_btn.click()
    assert not d._create_wt_panel.isVisibleTo(d)


def test_create_worktree_panel_create_and_add_calls_vm(qtbot):
    vm = _vm(statuses=[_status("/r/main")])
    vm.create_worktree_for_project.return_value = _status("/r/fix-auth", "fix/auth", is_main=False)
    d = _dlg(qtbot, vm=vm, repos={"/repos/proj": MagicMock()})

    toggle_btn = next(b for b in d.findChildren(QPushButton) if "Create new worktree" in b.text())
    toggle_btn.click()

    # Fill in the form
    wt_name_le = d._create_wt_panel.findChildren(QLineEdit)[0]
    branch_le = d._create_wt_panel.findChildren(QLineEdit)[1]
    wt_name_le.setText("fix-auth")
    branch_le.setText("fix/auth")

    create_btn = next(
        b for b in d._create_wt_panel.findChildren(QPushButton) if "Create" in b.text() and b.text() != "Cancel"
    )
    create_btn.click()

    vm.create_worktree_for_project.assert_called_once()


def test_create_worktree_panel_adds_to_entries_on_success(qtbot):
    vm = _vm(statuses=[_status("/r/main")])
    vm.create_worktree_for_project.return_value = _status("/r/fix-auth", "fix/auth", is_main=False)
    d = _dlg(qtbot, vm=vm, repos={"/repos/proj": MagicMock()})

    toggle_btn = next(b for b in d.findChildren(QPushButton) if "Create new worktree" in b.text())
    toggle_btn.click()

    wt_name_le = d._create_wt_panel.findChildren(QLineEdit)[0]
    branch_le = d._create_wt_panel.findChildren(QLineEdit)[1]
    wt_name_le.setText("fix-auth")
    branch_le.setText("fix/auth")

    create_btn = next(
        b for b in d._create_wt_panel.findChildren(QPushButton) if "Create" in b.text() and b.text() != "Cancel"
    )
    create_btn.click()

    qtbot.waitUntil(lambda: "/r/fix-auth" in d.get_entries(), timeout=3000)
    assert "/r/fix-auth" in d.get_entries()


def test_create_worktree_panel_collapses_after_success(qtbot):
    vm = _vm(statuses=[_status("/r/main")])
    vm.create_worktree_for_project.return_value = _status("/r/fix-auth", "fix/auth", is_main=False)
    d = _dlg(qtbot, vm=vm, repos={"/repos/proj": MagicMock()})

    toggle_btn = next(b for b in d.findChildren(QPushButton) if "Create new worktree" in b.text())
    toggle_btn.click()

    wt_name_le = d._create_wt_panel.findChildren(QLineEdit)[0]
    branch_le = d._create_wt_panel.findChildren(QLineEdit)[1]
    wt_name_le.setText("fix-auth")
    branch_le.setText("fix/auth")

    create_btn = next(
        b for b in d._create_wt_panel.findChildren(QPushButton) if "Create" in b.text() and b.text() != "Cancel"
    )
    create_btn.click()

    qtbot.waitUntil(lambda: not d._create_wt_panel.isVisibleTo(d), timeout=3000)
    assert not d._create_wt_panel.isVisibleTo(d)


def test_create_worktree_panel_shows_inline_error_on_failure(qtbot):
    vm = _vm(statuses=[_status("/r/main")])
    vm.create_worktree_for_project.side_effect = subprocess.CalledProcessError(
        128, "git", stderr="branch already exists"
    )
    d = _dlg(qtbot, vm=vm, repos={"/repos/proj": MagicMock()})

    toggle_btn = next(b for b in d.findChildren(QPushButton) if "Create new worktree" in b.text())
    toggle_btn.click()

    wt_name_le = d._create_wt_panel.findChildren(QLineEdit)[0]
    branch_le = d._create_wt_panel.findChildren(QLineEdit)[1]
    wt_name_le.setText("fix-auth")
    branch_le.setText("fix/auth")

    create_btn = next(
        b for b in d._create_wt_panel.findChildren(QPushButton) if "Create" in b.text() and b.text() != "Cancel"
    )
    create_btn.click()

    # Wait for error to appear (async), then check panel stays open and error shown
    qtbot.waitUntil(lambda: bool(d._create_wt_error.text()), timeout=3000)
    assert d._create_wt_panel.isVisibleTo(d)
    err_text = d._create_wt_error.text().lower()
    assert "error" in err_text or "branch already exists" in err_text


# ── [New branch here…] placeholder button ────────────────────────────────────

def test_new_branch_here_button_present_for_each_worktree_row(qtbot):
    statuses = [
        _status("/r/main", "main", is_main=True),
        _status("/r/feat", "feature/x", is_main=False),
    ]
    d = _dlg(qtbot, vm=_vm(statuses=statuses))
    btns = _button_texts(d)
    new_branch_btns = [t for t in btns if "New branch here" in t]
    assert len(new_branch_btns) >= 2
