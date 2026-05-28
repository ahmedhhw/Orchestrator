"""Tests for async loading behavior in BranchManagementPanel sync section."""
from unittest.mock import MagicMock

from PySide6.QtWidgets import QProgressBar, QLabel, QPushButton

from worktree_manager.branch_mgmt_vm import BranchRow, FetchResult, SyncResult
from worktree_manager.ui.branch_management_panel import BranchManagementPanel


def _row(branch="main", repo_path="/repo/a", has_upstream=True, behind=0):
    return BranchRow(
        repo_path=repo_path, branch=branch, has_upstream=has_upstream,
        ahead=0, behind=behind, worktree_path=None,
        has_uncommitted=False, excluded=False,
    )


def _make_vm(rows=None):
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = ["/repo/a"]
    mock_vm.load_cleanup_candidates.return_value = []
    mock_vm.load_syncable_branches.return_value = rows or [_row()]
    mock_vm.fetch_all.return_value = [FetchResult(repo_path="/repo/a", error=None)]
    mock_vm.sync_included.return_value = []
    mock_vm.sync_one.return_value = SyncResult(
        repo_path="/repo/a", branch="main", status="up_to_date"
    )
    return mock_vm


def _wait_loaded(qtbot, panel, timeout=2000):
    qtbot.waitUntil(lambda: not panel._sync_loading, timeout=timeout)


def test_sync_panel_shows_progress_bar_while_loading(qtbot):
    mock_vm = _make_vm()
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()

    assert panel._sync_loading is True
    assert panel.findChild(QProgressBar) is not None


def test_sync_panel_progress_bar_gone_after_load_completes(qtbot):
    mock_vm = _make_vm()
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()
    _wait_loaded(qtbot, panel)

    assert panel._sync_loading is False
    assert panel.findChild(QProgressBar) is None


def test_sync_panel_fetch_all_button_disabled_during_load(qtbot):
    mock_vm = _make_vm()
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()

    fetch_btn = next(
        (b for b in panel.findChildren(QPushButton) if "Fetch all" in b.text()), None
    )
    assert fetch_btn is not None
    assert not fetch_btn.isEnabled()


def test_sync_panel_sync_all_button_disabled_during_load(qtbot):
    mock_vm = _make_vm()
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()

    sync_btn = next(
        (b for b in panel.findChildren(QPushButton) if "Sync all" in b.text()), None
    )
    assert sync_btn is not None
    assert not sync_btn.isEnabled()


def test_sync_panel_buttons_re_enabled_after_load(qtbot):
    mock_vm = _make_vm()
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()
    _wait_loaded(qtbot, panel)

    fetch_btn = next(b for b in panel.findChildren(QPushButton) if "Fetch all" in b.text())
    sync_btn = next(b for b in panel.findChildren(QPushButton) if "Sync all" in b.text())
    assert fetch_btn.isEnabled()
    assert sync_btn.isEnabled()


def test_sync_panel_renders_branch_rows_after_load(qtbot):
    mock_vm = _make_vm(rows=[_row(branch="feature/billing")])
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()
    _wait_loaded(qtbot, panel)

    labels = [lbl.text() for lbl in panel.findChildren(QLabel)]
    assert any("feature/billing" in t for t in labels)


def test_sync_panel_shows_error_widget_on_vm_exception(qtbot):
    mock_vm = _make_vm()
    mock_vm.load_syncable_branches.side_effect = RuntimeError("git not found")
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()

    qtbot.waitUntil(lambda: not panel._sync_loading, timeout=2000)

    labels = [lbl.text() for lbl in panel.findChildren(QLabel)]
    assert any("git not found" in t or "error" in t.lower() for t in labels)


def test_sync_panel_shows_retry_button_on_error(qtbot):
    mock_vm = _make_vm()
    mock_vm.load_syncable_branches.side_effect = RuntimeError("network timeout")
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()

    qtbot.waitUntil(lambda: not panel._sync_loading, timeout=2000)

    buttons = [b.text() for b in panel.findChildren(QPushButton)]
    assert any("Retry" in t for t in buttons)
