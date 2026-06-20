"""
Behavioural tests for the async select_pr flow:
  - instant render from in-memory PR (no network on calling thread)
  - background refresh re-emits pr_detail_updated with fresher data
  - failed background refresh surfaces error; existing detail stays visible
  - no placeholder/flicker: selected_pr stays set until refresh lands
"""
import threading
import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck, Review
from worktree_manager.github_vm import GitHubViewModel


def _make_pr(number=1, sha="abc"):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/myorg/myrepo/pull/{number}",
        head_branch="feat", base_branch="main",
        state="open", draft=False, mergeable=True,
        head_sha=sha,
        checks=[CICheck("build", "completed", "success")],
    )


@pytest.fixture
def store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


@pytest.fixture
def vm(store, qtbot):
    from PySide6.QtWidgets import QApplication
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        svc = MagicMock()
        svc.fetch_all_open_prs.return_value = []
        MockSvc.return_value = svc
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    QApplication.processEvents()
    v._svc.get_pr_detail.reset_mock()
    yield v
    v.deleteLater()


# ── Test 1: instant render — no network on calling thread ─────────────────────

def test_select_pr_emits_detail_updated_immediately_without_network(vm, qtbot):
    """
    Selecting a PR must emit pr_detail_updated synchronously (before any
    background thread can complete) and must NOT call get_pr_detail on the
    calling thread.
    """
    pr = _make_pr(42)
    vm.prs = [pr]

    # Block any background thread from completing during this test by making
    # get_pr_detail block on an event we never set.
    gate = threading.Event()
    def _blocking_detail(*args, **kwargs):
        gate.wait(timeout=5)
        return _make_pr(42)
    vm._svc.get_pr_detail.side_effect = _blocking_detail

    signals_received = []

    def _on_signal():
        # At the moment the signal fires, get_pr_detail must NOT have been
        # called yet (background thread is blocked on gate).
        signals_received.append(vm._svc.get_pr_detail.call_count)

    vm.pr_detail_updated.connect(_on_signal)

    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(pr)

    # Signal fired and selected_pr is set to the in-memory pr
    assert vm.selected_pr is pr
    # The very first pr_detail_updated emission must have happened before
    # get_pr_detail was called (call_count was 0 at that moment)
    assert signals_received[0] == 0, (
        "pr_detail_updated fired after get_pr_detail was called — "
        "the calling thread blocked on the network"
    )
    gate.set()  # unblock background thread so it doesn't leak


# ── Test 2: background refresh re-emits pr_detail_updated ────────────────────

def test_select_pr_background_refresh_emits_updated_signal(vm, qtbot):
    """
    After the instant render, a background thread must call get_pr_detail
    once and re-emit pr_detail_updated with the fresher PR.
    """
    pr = _make_pr(42)
    refreshed = _make_pr(42)
    refreshed.reviews = [Review("alice", "APPROVED")]
    vm.prs = [pr]
    vm._svc.get_pr_detail.return_value = refreshed

    # waitSignals collects two emissions of pr_detail_updated:
    # [0] instant render, [1] background refresh
    with qtbot.waitSignals(
        [vm.pr_detail_updated, vm.pr_detail_updated],
        timeout=3000,
    ):
        vm.select_pr(pr)

    # After the refresh lands, selected_pr should be the refreshed object
    assert vm.selected_pr is refreshed
    assert vm._svc.get_pr_detail.call_count == 1


# ── Test 3: failed background refresh surfaces error; detail stays ────────────

def test_select_pr_background_refresh_failure_surfaces_error_and_keeps_detail(vm, qtbot):
    """
    When the background refresh raises, refresh_error must be emitted with
    the error message, and selected_pr must remain the originally shown PR.
    """
    pr = _make_pr(42)
    vm.prs = [pr]
    vm._svc.get_pr_detail.side_effect = RuntimeError("network timeout")

    error_messages = []
    vm.refresh_error.connect(error_messages.append)

    # First emission: instant render
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(pr)

    # Wait for the background refresh to surface the error
    with qtbot.waitSignal(vm.refresh_error, timeout=3000):
        pass

    assert "network timeout" in error_messages[0]
    # The original in-memory PR must still be selected — not cleared
    assert vm.selected_pr is pr


# ── Test 4: no flicker — selected_pr stays set between instant and refresh ────

def test_select_pr_selected_pr_never_cleared_between_instant_and_refresh(vm, qtbot):
    """
    Between the instant render and the background refresh landing,
    selected_pr must not be None at any point.
    """
    pr = _make_pr(42)
    refreshed = _make_pr(42)
    vm.prs = [pr]

    gate = threading.Event()
    def _slow_detail(*args, **kwargs):
        gate.wait(timeout=5)
        return refreshed
    vm._svc.get_pr_detail.side_effect = _slow_detail

    selected_pr_values = []

    def _on_signal():
        selected_pr_values.append(vm.selected_pr)

    vm.pr_detail_updated.connect(_on_signal)

    # Wait for the instant render
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=1000):
        vm.select_pr(pr)

    # At the instant-render emission, selected_pr must be set (not None)
    assert selected_pr_values[0] is pr

    # Release background thread and wait for refresh emission
    gate.set()
    with qtbot.waitSignal(vm.pr_detail_updated, timeout=3000):
        pass

    # After refresh, selected_pr is the refreshed object
    assert vm.selected_pr is refreshed
    # All recorded values were non-None (no flicker)
    assert all(v is not None for v in selected_pr_values)
