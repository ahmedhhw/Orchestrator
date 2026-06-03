"""Behavioral contract — Iteration 0: Branch Management panel.

Concurrent per-row sync + cleanup repo label in 'all repos' view.
Run: python3.14 -m pytest tests/test_branch_mgmt_iter0_contract.py
"""
import threading
from unittest.mock import MagicMock

from PySide6.QtWidgets import QCheckBox, QLabel, QProgressBar, QPushButton

from worktree_manager.branch_mgmt_vm import BranchMgmtViewModel, BranchRow, SyncResult
from worktree_manager.models import CleanupCandidate
from worktree_manager.ui.branch_management_panel import BranchManagementPanel


# ── helpers ───────────────────────────────────────────────────────────────────

def _row(branch="main", repo_path="/repo/a", has_upstream=True, behind=2,
         worktree_path=None, has_uncommitted=False, excluded=False):
    return BranchRow(
        repo_path=repo_path, branch=branch, has_upstream=has_upstream,
        ahead=0, behind=behind, worktree_path=worktree_path,
        has_uncommitted=has_uncommitted, excluded=excluded,
    )


def _candidate(branch, repo_path=None, path=None, is_merged=False, is_stale=False,
               last_commit_ts=100000, merged_into=None, has_uncommitted=False,
               is_checked_out=False, is_protected=False):
    return CleanupCandidate(
        branch=branch, path=path, is_merged=is_merged, is_stale=is_stale,
        last_commit_ts=last_commit_ts, merged_into=merged_into,
        has_uncommitted=has_uncommitted, is_checked_out=is_checked_out,
        is_protected=is_protected, repo_path=repo_path,
    )


def _sync_panel(qtbot, rows):
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = sorted({r.repo_path for r in rows})
    mock_vm.load_cleanup_candidates.return_value = []
    mock_vm.load_syncable_branches.return_value = rows
    mock_vm.sync_one.return_value = SyncResult(
        repo_path="/repo/a", branch="main", status="up_to_date"
    )
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_sync()
    qtbot.waitUntil(lambda: not panel._sync_loading, timeout=2000)
    return panel, mock_vm


def _cleanup_panel(qtbot, candidates_by_repo, initial_repo=None):
    mock_vm = MagicMock()
    mock_vm.list_repos.return_value = list(candidates_by_repo.keys())

    def _load(repo_path, on_progress=None):
        if repo_path is None:
            out = []
            for cs in candidates_by_repo.values():
                out.extend(cs)
            return out
        return candidates_by_repo.get(repo_path, [])

    mock_vm.load_cleanup_candidates.side_effect = _load
    panel = BranchManagementPanel(vm=mock_vm)
    qtbot.addWidget(panel)
    panel.show_cleanup(repo_path=initial_repo)
    qtbot.waitUntil(lambda: not panel._cleanup_loading, timeout=2000)
    return panel, mock_vm


def _sync_row_buttons(panel):
    return [b for b in panel.findChildren(QPushButton) if b.text() == "Sync"]


def _label_texts(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def _checkbox_texts(widget):
    return [cb.text() for cb in widget.findChildren(QCheckBox)]


# ── 1 · Concurrent per-row sync ────────────────────────────────────────────────

def test_two_rows_can_sync_at_the_same_time(qtbot):
    """Clicking Sync on a second row while the first is mid-sync still calls the
    view-model for the second row — the click is not silently dropped."""
    gate = threading.Event()
    calls = []

    def slow_sync_one(repo_path, branch, worktree_path):
        calls.append(branch)
        gate.wait(timeout=2)
        return SyncResult(repo_path=repo_path, branch=branch, status="up_to_date")

    rows = [_row(branch="fix/login", repo_path="/repo/a"),
            _row(branch="chore/deps", repo_path="/repo/a")]
    panel, mock_vm = _sync_panel(qtbot, rows)
    mock_vm.sync_one.side_effect = slow_sync_one

    btns = _sync_row_buttons(panel)
    assert len(btns) == 2
    btns[0].click()
    btns[1].click()  # second click while first is still blocked on the gate

    # both rows are now in flight — both buttons disabled, both VM calls made
    qtbot.waitUntil(lambda: len(calls) == 2, timeout=2000)
    assert not btns[0].isEnabled()
    assert not btns[1].isEnabled()

    gate.set()
    qtbot.waitUntil(lambda: btns[0].isEnabled() and btns[1].isEnabled(), timeout=3000)


def test_concurrent_sync_updates_each_rows_own_status(qtbot):
    """Each row's status label reflects its own sync result, not a shared one."""
    rows = [_row(branch="fix/login", repo_path="/repo/a"),
            _row(branch="chore/deps", repo_path="/repo/a")]
    panel, mock_vm = _sync_panel(qtbot, rows)

    def result_for(repo_path, branch, worktree_path):
        status = "pulled" if branch == "fix/login" else "up_to_date"
        return SyncResult(repo_path=repo_path, branch=branch, status=status,
                          new_commits=3 if status == "pulled" else 0)

    mock_vm.sync_one.side_effect = result_for
    btns = _sync_row_buttons(panel)
    btns[0].click()
    btns[1].click()
    qtbot.waitUntil(
        lambda: btns[0].isEnabled() and btns[1].isEnabled(), timeout=3000
    )

    texts = _label_texts(panel)
    assert any("pulled" in t.lower() for t in texts)
    assert any("up to date" in t.lower() for t in texts)


def test_clicking_same_row_twice_while_running_calls_vm_once(qtbot):
    """A repeat click on a row that is already syncing is ignored (no double-run)."""
    gate = threading.Event()
    calls = []

    def slow_sync_one(repo_path, branch, worktree_path):
        calls.append(branch)
        gate.wait(timeout=2)
        return SyncResult(repo_path=repo_path, branch=branch, status="up_to_date")

    rows = [_row(branch="fix/login", repo_path="/repo/a")]
    panel, mock_vm = _sync_panel(qtbot, rows)
    mock_vm.sync_one.side_effect = slow_sync_one

    btn = _sync_row_buttons(panel)[0]
    btn.click()
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=2000)
    btn.click()  # second click on the same, already-syncing row

    gate.set()
    qtbot.waitUntil(lambda: btn.isEnabled(), timeout=3000)
    assert len(calls) == 1


def test_sync_all_still_runs_and_updates_status(qtbot):
    """Regression: the header 'Sync all' button still works."""
    rows = [_row(branch="main", repo_path="/repo/a")]
    panel, mock_vm = _sync_panel(qtbot, rows)
    mock_vm.sync_included.return_value = [
        SyncResult(repo_path="/repo/a", branch="main", status="pulled", new_commits=2)
    ]
    sync_all = next(b for b in panel.findChildren(QPushButton) if "Sync all" in b.text())
    sync_all.click()
    qtbot.waitUntil(lambda: not panel._action_running, timeout=3000)
    assert any("pulled" in t.lower() for t in _label_texts(panel))


# ── 2 · Cleanup repo label ──────────────────────────────────────────────────────

def test_all_repos_view_shows_repo_name_on_each_branch_row(qtbot):
    """With 'all repos' selected, each branch row label includes its repo name."""
    by_repo = {
        "/repo/my-app": [_candidate("fix/login", repo_path="/repo/my-app",
                                     is_merged=True, merged_into="main")],
        "/repo/billing-svc": [_candidate("hotfix/crash", repo_path="/repo/billing-svc",
                                          is_merged=True, merged_into="main")],
    }
    panel, _ = _cleanup_panel(qtbot, by_repo, initial_repo=None)

    texts = _checkbox_texts(panel)
    assert any("fix/login" in t and "my-app" in t for t in texts)
    assert any("hotfix/crash" in t and "billing-svc" in t for t in texts)


def test_single_repo_view_does_not_show_repo_name(qtbot):
    """With a single repo selected, rows do NOT carry the repo-name suffix."""
    by_repo = {
        "/repo/my-app": [_candidate("fix/login", repo_path="/repo/my-app",
                                     is_merged=True, merged_into="main")],
    }
    panel, _ = _cleanup_panel(qtbot, by_repo, initial_repo="/repo/my-app")

    texts = _checkbox_texts(panel)
    row = next(t for t in texts if "fix/login" in t)
    assert "my-app" not in row


def test_candidate_carries_repo_path_after_load():
    """Observable on the model: a loaded candidate knows which repo it came from.
    (Replaces the old _candidate_repo private-dict assertion.)"""
    from unittest.mock import patch
    store = MagicMock()
    store.all_repos.return_value = {"/repo/a": MagicMock(stale_days=30)}
    git = MagicMock()
    vm = BranchMgmtViewModel(config_store=store, git_service=git)
    c = _candidate("fix/thing", is_merged=True, merged_into="main")

    with patch("worktree_manager.branch_mgmt_vm.MainWindowViewModel") as MockVM:
        m = MagicMock()
        m.load_worktrees.return_value = []
        m.all_cleanup_candidates.return_value = [c]
        MockVM.return_value = m
        result = vm.load_cleanup_candidates(repo_path="/repo/a")

    assert result[0].repo_path == "/repo/a"


def test_delete_in_all_repos_routes_by_candidate_repo_path():
    """Deletes route to each candidate's own repo via repo_path — correct even when
    two repos share a branch name."""
    from unittest.mock import patch
    store = MagicMock()
    store.all_repos.return_value = {
        "/repo/a": MagicMock(stale_days=30),
        "/repo/b": MagicMock(stale_days=30),
    }
    git = MagicMock()
    vm = BranchMgmtViewModel(config_store=store, git_service=git)

    # SAME branch name in both repos — the bug the old branch-keyed dict had.
    c_a = _candidate("shared/branch", repo_path="/repo/a", is_merged=True, merged_into="main")
    c_b = _candidate("shared/branch", repo_path="/repo/b", is_stale=True)

    repo_vms: dict[str, MagicMock] = {}

    with patch("worktree_manager.branch_mgmt_vm.MainWindowViewModel") as MockVM:
        def _side_effect(repo_path, config_store, git_service):
            m = MagicMock()
            m.load_worktrees.return_value = []
            m.all_cleanup_candidates.return_value = (
                [c_a] if repo_path == "/repo/a" else [c_b]
            )
            repo_vms[repo_path] = m
            return m
        MockVM.side_effect = _side_effect
        vm.load_cleanup_candidates(repo_path=None)
        vm.delete_cleanup_selection(repo_path=None, candidates=[c_a, c_b])

    repo_vms["/repo/a"].delete_cleanup_candidates.assert_called_once_with(
        [c_a], also_delete_branches=True
    )
    repo_vms["/repo/b"].delete_cleanup_candidates.assert_called_once_with(
        [c_b], also_delete_branches=True
    )
