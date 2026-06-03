"""Tests for async Sync panel toolbar and per-row actions (Iteration 1)."""
from unittest.mock import MagicMock, call

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QProgressBar

from worktree_manager.branch_mgmt_vm import BranchRow, FetchResult, SyncResult
from worktree_manager.ui.branch_management_panel import BranchManagementPanel


def _row(branch="main", repo_path="/repo/a", has_upstream=True, behind=2,
         worktree_path=None, has_uncommitted=False, excluded=False):
    return BranchRow(
        repo_path=repo_path, branch=branch, has_upstream=has_upstream,
        ahead=0, behind=behind, worktree_path=worktree_path,
        has_uncommitted=has_uncommitted, excluded=excluded,
    )


def _make_panel(qtbot, rows=None, fetch_results=None, sync_results=None):
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = ["/repo/a"]
    mock_vm.load_cleanup_candidates.return_value = []
    mock_vm.load_syncable_branches.return_value = rows or [_row()]
    mock_vm.fetch_all.return_value = fetch_results or [FetchResult(repo_path="/repo/a", error=None)]
    mock_vm.sync_included.return_value = sync_results or []
    mock_vm.sync_one.return_value = SyncResult(
        repo_path="/repo/a", branch="main", status="up_to_date"
    )
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()
    qtbot.waitUntil(lambda: not panel._sync_loading, timeout=2000)
    return panel, mock_vm


def _wait_action(qtbot, panel, timeout=3000):
    """Wait until no async action is in flight."""
    qtbot.waitUntil(lambda: not panel._action_running, timeout=timeout)


def _buttons(widget):
    return widget.findChildren(QPushButton)


def _button_texts(widget):
    return [b.text() for b in _buttons(widget)]


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


# ── InlineProgress.mini() ─────────────────────────────────────────────────────

def test_mini_progress_has_progress_bar(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress
    from PySide6.QtWidgets import QApplication
    mini = InlineProgress.mini()
    qtbot.addWidget(mini)
    assert mini.findChild(QProgressBar) is not None


def test_mini_progress_has_label(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress
    mini = InlineProgress.mini()
    qtbot.addWidget(mini)
    assert mini.findChild(QLabel) is not None


def test_mini_progress_start_indeterminate_sets_range_zero(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress
    mini = InlineProgress.mini()
    qtbot.addWidget(mini)
    mini.start_indeterminate("syncing…")
    bar = mini.findChild(QProgressBar)
    assert bar.minimum() == 0 and bar.maximum() == 0


def test_mini_progress_start_determinate_sets_range(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress
    mini = InlineProgress.mini()
    qtbot.addWidget(mini)
    mini.start_determinate("Fetching…", total=4)
    bar = mini.findChild(QProgressBar)
    assert bar.maximum() == 4


def test_mini_progress_update_advances_value(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress
    mini = InlineProgress.mini()
    qtbot.addWidget(mini)
    mini.start_determinate("Fetching…", total=4)
    mini.update(2, "repo-b")
    bar = mini.findChild(QProgressBar)
    assert bar.value() == 2


# ── fetch_all on_progress ─────────────────────────────────────────────────────

def test_fetch_all_vm_accepts_on_progress():
    from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel
    import inspect
    sig = inspect.signature(BranchMgmtViewModel.fetch_all)
    assert "on_progress" in sig.parameters


def test_fetch_all_emits_progress_per_repo():
    from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel
    from unittest.mock import MagicMock, patch
    vm = MagicMock(spec=BranchMgmtViewModel)
    vm.list_repos.return_value = ["/repo/a", "/repo/b"]

    calls = []
    def fake_fetch_all(on_progress=None):
        for i, path in enumerate(["/repo/a", "/repo/b"], start=1):
            if on_progress:
                on_progress(i, 2, path)
        return []
    vm.fetch_all.side_effect = fake_fetch_all
    vm.fetch_all(on_progress=lambda cur, tot, lbl: calls.append((cur, tot, lbl)))
    assert len(calls) == 2
    assert calls[0] == (1, 2, "/repo/a")
    assert calls[1] == (2, 2, "/repo/b")


# ── sync_included on_progress ─────────────────────────────────────────────────

def test_sync_included_vm_accepts_on_progress():
    from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel
    import inspect
    sig = inspect.signature(BranchMgmtViewModel.sync_included)
    assert "on_progress" in sig.parameters


# ── toolbar fetch all async ───────────────────────────────────────────────────

def test_fetch_all_runs_async_calls_vm(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    fetch_btn = next(b for b in _buttons(panel) if "Fetch all" in b.text())
    fetch_btn.click()
    _wait_action(qtbot, panel)
    mock_vm.fetch_all.assert_called()


def test_fetch_all_disables_both_buttons_while_running(qtbot):
    """Both Fetch and Sync all buttons disabled during fetch."""
    panel, mock_vm = _make_panel(qtbot)

    # Make fetch_all block until we check button state
    import threading
    gate = threading.Event()
    original = mock_vm.fetch_all.side_effect

    def slow_fetch(on_progress=None):
        gate.wait(timeout=2)
        return [FetchResult(repo_path="/repo/a", error=None)]

    mock_vm.fetch_all.side_effect = slow_fetch

    fetch_btn = next(b for b in _buttons(panel) if "Fetch all" in b.text())
    fetch_btn.click()

    # While gate is held — both buttons should be disabled
    assert not fetch_btn.isEnabled()
    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    assert not sync_btn.isEnabled()

    gate.set()
    _wait_action(qtbot, panel)


def test_fetch_all_re_enables_buttons_after_completion(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    fetch_btn = next(b for b in _buttons(panel) if "Fetch all" in b.text())
    fetch_btn.click()
    _wait_action(qtbot, panel)
    assert fetch_btn.isEnabled()
    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    assert sync_btn.isEnabled()


def test_fetch_all_updates_last_fetch_label(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    fetch_btn = next(b for b in _buttons(panel) if "Fetch all" in b.text())
    fetch_btn.click()
    _wait_action(qtbot, panel)
    assert any("last fetch" in t.lower() for t in _label_texts(panel))


# ── toolbar sync all async ────────────────────────────────────────────────────

def test_sync_all_runs_async_calls_vm(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    sync_btn.click()
    _wait_action(qtbot, panel)
    mock_vm.sync_included.assert_called()


def test_sync_all_disables_both_buttons_while_running(qtbot):
    import threading
    gate = threading.Event()

    def slow_sync(on_progress=None):
        gate.wait(timeout=2)
        return []

    panel, mock_vm = _make_panel(qtbot)
    mock_vm.sync_included.side_effect = slow_sync

    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    sync_btn.click()

    assert not sync_btn.isEnabled()
    fetch_btn = next(b for b in _buttons(panel) if "Fetch all" in b.text())
    assert not fetch_btn.isEnabled()

    gate.set()
    _wait_action(qtbot, panel)


def test_sync_all_re_enables_buttons_after_completion(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    sync_btn.click()
    _wait_action(qtbot, panel)
    assert sync_btn.isEnabled()
    fetch_btn = next(b for b in _buttons(panel) if "Fetch all" in b.text())
    assert fetch_btn.isEnabled()


def test_sync_all_applies_results_to_status_labels(qtbot):
    row = _row(branch="main", has_upstream=True)
    results = [SyncResult(repo_path="/repo/a", branch="main", status="pulled", new_commits=3)]
    panel, mock_vm = _make_panel(qtbot, rows=[row], sync_results=results)

    sync_btn = next(b for b in _buttons(panel) if "Sync all" in b.text())
    sync_btn.click()
    _wait_action(qtbot, panel)

    assert any("pulled" in t.lower() for t in _label_texts(panel))


# ── per-row sync async ────────────────────────────────────────────────────────

def test_per_row_sync_runs_async_calls_vm(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    sync_row_btn = next(b for b in _buttons(panel) if b.text() == "Sync")
    sync_row_btn.click()
    qtbot.waitUntil(lambda: mock_vm.sync_one.called, timeout=3000)
    mock_vm.sync_one.assert_called_once()


def test_per_row_sync_button_disabled_while_running(qtbot):
    import threading
    gate = threading.Event()

    def slow_sync_one(**kwargs):
        gate.wait(timeout=2)
        return SyncResult(repo_path="/repo/a", branch="main", status="up_to_date")

    panel, mock_vm = _make_panel(qtbot)
    mock_vm.sync_one.side_effect = slow_sync_one

    sync_row_btn = next(b for b in _buttons(panel) if b.text() == "Sync")
    sync_row_btn.click()

    assert not sync_row_btn.isEnabled()
    gate.set()
    _wait_action(qtbot, panel)


def test_per_row_sync_button_re_enabled_after_completion(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    sync_row_btn = next(b for b in _buttons(panel) if b.text() == "Sync")
    sync_row_btn.click()
    # per-row syncs are tracked individually, not by _action_running
    qtbot.waitUntil(lambda: sync_row_btn.isEnabled(), timeout=3000)
    assert sync_row_btn.isEnabled()


def test_per_row_sync_updates_status_label(qtbot):
    panel, mock_vm = _make_panel(qtbot)
    mock_vm.sync_one.return_value = SyncResult(
        repo_path="/repo/a", branch="main", status="pulled", new_commits=2
    )
    sync_row_btn = next(b for b in _buttons(panel) if b.text() == "Sync")
    sync_row_btn.click()
    qtbot.waitUntil(lambda: sync_row_btn.isEnabled(), timeout=3000)

    assert any("pulled" in t.lower() for t in _label_texts(panel))


def test_per_row_sync_shows_mini_bar_in_row_while_running(qtbot):
    """A QProgressBar appears within the row while sync_one is running."""
    import threading
    gate = threading.Event()

    def slow_sync_one(**kwargs):
        gate.wait(timeout=2)
        return SyncResult(repo_path="/repo/a", branch="main", status="up_to_date")

    panel, mock_vm = _make_panel(qtbot)
    mock_vm.sync_one.side_effect = slow_sync_one

    sync_row_btn = next(b for b in _buttons(panel) if b.text() == "Sync")
    sync_row_btn.click()

    assert panel.findChild(QProgressBar) is not None
    gate.set()
    _wait_action(qtbot, panel)
