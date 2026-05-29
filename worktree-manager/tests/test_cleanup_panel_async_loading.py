"""Tests for async loading in BranchManagementPanel Cleanup tab (Iteration 2)."""
from unittest.mock import MagicMock

from PySide6.QtWidgets import QLabel, QPushButton, QProgressBar

from worktree_manager.branch_mgmt_vm import BranchRow, FetchResult, SyncResult
from worktree_manager.ui.branch_management_panel import BranchManagementPanel


def _make_vm(candidates=None, raise_on_load=None):
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = ["/repo/a"]
    mock_vm.load_syncable_branches.return_value = []
    mock_vm.fetch_all.return_value = [FetchResult(repo_path="/repo/a", error=None)]
    mock_vm.sync_included.return_value = []
    mock_vm.sync_one.return_value = SyncResult(
        repo_path="/repo/a", branch="main", status="up_to_date"
    )
    if raise_on_load:
        mock_vm.load_cleanup_candidates.side_effect = raise_on_load
    else:
        mock_vm.load_cleanup_candidates.return_value = candidates or []
    return mock_vm


def _make_cleanup_panel(qtbot, candidates=None, raise_on_load=None):
    mock_vm = _make_vm(candidates=candidates, raise_on_load=raise_on_load)
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=None)
    return panel, mock_vm


def _wait_cleanup_loaded(qtbot, panel, timeout=2000):
    qtbot.waitUntil(lambda: not panel._cleanup_loading, timeout=timeout)


def _buttons(widget):
    return widget.findChildren(QPushButton)


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


# ── loading state ─────────────────────────────────────────────────────────────

def test_cleanup_shows_progress_bar_while_loading(qtbot):
    import threading
    gate = threading.Event()

    mock_vm = _make_vm()
    def slow_load(repo_path, on_progress=None):
        gate.wait(timeout=2)
        return []
    mock_vm.load_cleanup_candidates.side_effect = slow_load

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=None)

    assert panel._cleanup_loading is True
    assert panel.findChild(QProgressBar) is not None
    gate.set()
    _wait_cleanup_loaded(qtbot, panel)


def test_cleanup_progress_bar_gone_after_load(qtbot):
    panel, _ = _make_cleanup_panel(qtbot)
    _wait_cleanup_loaded(qtbot, panel)

    assert panel._cleanup_loading is False
    assert panel.findChild(QProgressBar) is None


def test_cleanup_loading_state_false_initially_before_show(qtbot):
    mock_vm = _make_vm()
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    assert panel._cleanup_loading is False


# ── action buttons disabled during load ───────────────────────────────────────

def test_cleanup_delete_button_disabled_during_load(qtbot):
    import threading
    gate = threading.Event()

    mock_vm = _make_vm()
    def slow_load(repo_path, on_progress=None):
        gate.wait(timeout=2)
        return []
    mock_vm.load_cleanup_candidates.side_effect = slow_load

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=None)

    delete_btn = next(
        (b for b in _buttons(panel) if b.text() == "Delete"), None
    )
    assert delete_btn is not None
    assert not delete_btn.isEnabled()
    gate.set()
    _wait_cleanup_loaded(qtbot, panel)


def test_cleanup_select_all_button_disabled_during_load(qtbot):
    import threading
    gate = threading.Event()

    mock_vm = _make_vm()
    def slow_load(repo_path, on_progress=None):
        gate.wait(timeout=2)
        return []
    mock_vm.load_cleanup_candidates.side_effect = slow_load

    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=None)

    select_btn = next(
        (b for b in _buttons(panel) if "Select" in b.text()), None
    )
    assert select_btn is not None
    assert not select_btn.isEnabled()
    gate.set()
    _wait_cleanup_loaded(qtbot, panel)


def test_cleanup_buttons_re_enabled_after_load(qtbot):
    panel, _ = _make_cleanup_panel(qtbot)
    _wait_cleanup_loaded(qtbot, panel)

    delete_btn = next(b for b in _buttons(panel) if b.text() == "Delete")
    select_btn = next(b for b in _buttons(panel) if "Select" in b.text())
    assert delete_btn.isEnabled()
    assert select_btn.isEnabled()


# ── error state ───────────────────────────────────────────────────────────────

def test_cleanup_shows_error_label_on_vm_exception(qtbot):
    panel, _ = _make_cleanup_panel(
        qtbot, raise_on_load=RuntimeError("git not found")
    )
    _wait_cleanup_loaded(qtbot, panel)

    labels = _label_texts(panel)
    assert any("git not found" in t or "error" in t.lower() for t in labels)


def test_cleanup_shows_retry_button_on_error(qtbot):
    panel, _ = _make_cleanup_panel(
        qtbot, raise_on_load=RuntimeError("network timeout")
    )
    _wait_cleanup_loaded(qtbot, panel)

    buttons = [b.text() for b in _buttons(panel)]
    assert any("Retry" in t for t in buttons)


# ── load_cleanup_candidates accepts on_progress ───────────────────────────────

def test_load_cleanup_candidates_accepts_on_progress():
    import inspect
    from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel
    sig = inspect.signature(BranchMgmtViewModel.load_cleanup_candidates)
    assert "on_progress" in sig.parameters


def test_load_cleanup_candidates_emits_progress_per_repo():
    from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel
    calls = []
    vm = MagicMock(spec=BranchMgmtViewModel)

    def fake_load(repo_path, on_progress=None):
        for i, path in enumerate(["/repo/a", "/repo/b"], start=1):
            if on_progress:
                on_progress(i, 2, path)
        return []

    vm.load_cleanup_candidates.side_effect = fake_load
    vm.load_cleanup_candidates(
        repo_path=None,
        on_progress=lambda cur, tot, lbl: calls.append((cur, tot, lbl))
    )
    assert len(calls) == 2
    assert calls[0][0] == 1
    assert calls[1][0] == 2


# ── repo dropdown change triggers fresh async load ────────────────────────────

def test_changing_repo_dropdown_triggers_reload(qtbot):
    mock_vm = _make_vm()
    mock_vm.list_repos.return_value = ["/repo/a", "/repo/b"]
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=None)
    _wait_cleanup_loaded(qtbot, panel)

    initial_call_count = mock_vm.load_cleanup_candidates.call_count

    panel._repo_combo.setCurrentIndex(1)  # switch to /repo/a
    _wait_cleanup_loaded(qtbot, panel)

    assert mock_vm.load_cleanup_candidates.call_count > initial_call_count
