"""Tests for the Sync from origin section of BranchManagementPanel (Iteration 2)."""
from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton

from worktree_manager.branch_mgmt_vm import BranchRow, FetchResult, SyncResult
from worktree_manager.ui.branch_management_panel import BranchManagementPanel


def _row(
    repo_path="/repo/a",
    branch="main",
    has_upstream=True,
    ahead=0,
    behind=2,
    worktree_path=None,
    has_uncommitted=False,
    excluded=False,
):
    return BranchRow(
        repo_path=repo_path,
        branch=branch,
        has_upstream=has_upstream,
        ahead=ahead,
        behind=behind,
        worktree_path=worktree_path,
        has_uncommitted=has_uncommitted,
        excluded=excluded,
    )


def _make_panel(qtbot, rows=None, sync_results=None):
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = ["/repo/a"]
    mock_vm.load_cleanup_candidates.return_value = []
    mock_vm.load_syncable_branches.return_value = rows or [_row()]
    mock_vm.fetch_all.return_value = [FetchResult(repo_path="/repo/a", error=None)]
    mock_vm.sync_included.return_value = sync_results or []
    mock_vm.sync_one.return_value = SyncResult(
        repo_path="/repo/a", branch="main", status="up_to_date"
    )

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()
    qtbot.waitUntil(lambda: not panel._sync_loading, timeout=2000)
    return panel, mock_vm


def _buttons(widget):
    return widget.findChildren(QPushButton)


def _button_texts(widget):
    return [b.text() for b in _buttons(widget)]


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def _checkboxes(widget):
    return widget.findChildren(QCheckBox)


# ── section switching ─────────────────────────────────────────────────────────

def test_show_sync_activates_sync_tab(qtbot):
    panel, _ = _make_panel(qtbot)
    sync_btn = next(b for b in _buttons(panel) if "Sync from origin" in b.text())
    assert sync_btn.isChecked()


def test_sync_section_no_longer_shows_coming_soon(qtbot):
    panel, _ = _make_panel(qtbot)
    assert not any("Coming soon" in t for t in _label_texts(panel))


# ── action buttons ────────────────────────────────────────────────────────────

def test_fetch_all_button_present(qtbot):
    panel, _ = _make_panel(qtbot)
    assert any("Fetch all" in t for t in _button_texts(panel))


def test_sync_all_button_present(qtbot):
    panel, _ = _make_panel(qtbot)
    assert any("Sync all" in t for t in _button_texts(panel))


def test_fetch_all_button_calls_vm(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    fetch_btn = next(b for b in _buttons(panel) if "Fetch all" in b.text())
    fetch_btn.click()
    mock_vm.fetch_all.assert_called_once()


def test_sync_all_button_calls_vm(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    sync_btn.click()
    mock_vm.sync_included.assert_called_once()


# ── branch rows ───────────────────────────────────────────────────────────────

def test_branch_name_shown_in_row(qtbot):
    panel, _ = _make_panel(qtbot, rows=[_row(branch="feature/x")])
    assert any("feature/x" in t for t in _label_texts(panel))


def test_behind_count_shown(qtbot):
    panel, _ = _make_panel(qtbot, rows=[_row(behind=5)])
    assert any("5" in t for t in _label_texts(panel))


def test_no_upstream_row_shows_label(qtbot):
    panel, _ = _make_panel(qtbot, rows=[_row(branch="orphan", has_upstream=False)])
    assert any("no upstream" in t.lower() for t in _label_texts(panel))


def test_per_row_sync_button_present_when_has_upstream(qtbot):
    panel, _ = _make_panel(qtbot, rows=[_row(branch="main", has_upstream=True)])
    # There should be a small per-row sync button with exactly "Sync" text
    per_row_sync_btns = [b for b in _buttons(panel) if b.text() == "Sync"]
    assert len(per_row_sync_btns) == 1


def test_no_per_row_sync_button_when_no_upstream(qtbot):
    panel, _ = _make_panel(qtbot, rows=[_row(branch="orphan", has_upstream=False)])
    # No per-row "Sync" button for branches without upstream
    per_row_sync_btns = [b for b in _buttons(panel) if b.text() == "Sync"]
    assert len(per_row_sync_btns) == 0


def test_per_row_sync_button_calls_sync_one(qtbot):
    row = _row(branch="main", has_upstream=True, worktree_path=None)
    panel, mock_vm = _make_panel(qtbot, rows=[row])
    sync_row_btn = next(b for b in _buttons(panel) if b.text() == "Sync")
    sync_row_btn.click()
    mock_vm.sync_one.assert_called_once_with(
        repo_path="/repo/a", branch="main", worktree_path=None
    )


def test_include_checkbox_present_for_each_branch(qtbot):
    rows = [_row(branch="main"), _row(branch="feature/x", repo_path="/repo/a")]
    panel, _ = _make_panel(qtbot, rows=rows)
    cbs = _checkboxes(panel)
    # At least one checkbox per branch row (exclude checkboxes for non-admin rows)
    assert len(cbs) >= 2


def test_excluded_row_checkbox_unchecked(qtbot):
    row = _row(branch="feature/x", excluded=True)
    panel, _ = _make_panel(qtbot, rows=[row])
    cbs = _checkboxes(panel)
    assert any(not cb.isChecked() for cb in cbs)


def test_included_row_checkbox_checked(qtbot):
    row = _row(branch="main", excluded=False)
    panel, _ = _make_panel(qtbot, rows=[row])
    cbs = _checkboxes(panel)
    assert any(cb.isChecked() for cb in cbs)


def test_toggling_checkbox_calls_set_excluded(qtbot):
    row = _row(branch="main", excluded=False)
    panel, mock_vm = _make_panel(qtbot, rows=[row])
    cb = next(
        (cb for cb in _checkboxes(panel) if cb.isChecked()), None
    )
    assert cb is not None
    cb.setChecked(False)
    mock_vm.set_excluded.assert_called()


# ── status badges after sync ──────────────────────────────────────────────────

def test_sync_all_updates_status_badge_up_to_date(qtbot):
    row = _row(branch="main", has_upstream=True)
    sync_results = [SyncResult(repo_path="/repo/a", branch="main", status="up_to_date")]
    panel, mock_vm = _make_panel(qtbot, rows=[row], sync_results=sync_results)

    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    sync_btn.click()

    assert any("up to date" in t.lower() for t in _label_texts(panel))


def test_sync_all_updates_status_badge_dirty(qtbot):
    row = _row(branch="main", has_upstream=True, has_uncommitted=True)
    sync_results = [SyncResult(repo_path="/repo/a", branch="main", status="dirty")]
    panel, mock_vm = _make_panel(qtbot, rows=[row], sync_results=sync_results)

    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    sync_btn.click()

    assert any("dirty" in t.lower() for t in _label_texts(panel))


def test_sync_all_updates_status_badge_pulled(qtbot):
    row = _row(branch="main", has_upstream=True, behind=3)
    sync_results = [SyncResult(repo_path="/repo/a", branch="main", status="pulled", new_commits=3)]
    panel, mock_vm = _make_panel(qtbot, rows=[row], sync_results=sync_results)

    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    sync_btn.click()

    assert any("pulled" in t.lower() for t in _label_texts(panel))


# ── last fetch footer ─────────────────────────────────────────────────────────

def test_last_fetch_label_shown_after_fetch(qtbot):
    panel, _ = _make_panel(qtbot)
    fetch_btn = next(b for b in _buttons(panel) if "Fetch all" in b.text())
    fetch_btn.click()
    assert any("last fetch" in t.lower() for t in _label_texts(panel))


# ── regression: cleanup section still reachable ───────────────────────────────

def test_cleanup_tab_still_switches_after_sync_shown(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    mock_vm.load_cleanup_candidates.return_value = []

    cleanup_btn = next(b for b in _buttons(panel) if b.text() == "Cleanup")
    cleanup_btn.click()

    assert cleanup_btn.isChecked()
