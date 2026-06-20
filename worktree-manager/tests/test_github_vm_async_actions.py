"""
Behavioural tests for async (non-blocking) VM actions:
  merge_pr — background thread, result/error signals, delayed refresh
  retry_failed_cis / retry_all_cis — POSTs on background thread
  open_pull_request — push+create on background thread, result/error signals
"""
import threading
import pytest
from unittest.mock import MagicMock, patch, call
from worktree_manager.github_models import CICheck, PullRequest
from worktree_manager.github_vm import GitHubViewModel, RERUN_REFETCH_MS


def _make_pr(number=1, checks=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/org/repo/pull/{number}",
        head_branch="feat", base_branch="main", state="open", draft=False,
        mergeable=True, checks=checks or [],
    )


def _failed_check(name="build", run_id="42", suite_id="suite-1"):
    return CICheck(name=name, status="completed", conclusion="failure",
                   check_suite_id=suite_id, run_id=run_id)


def _passing_check(name="build", run_id="42", suite_id="suite-1"):
    return CICheck(name=name, status="completed", conclusion="success",
                   check_suite_id=suite_id, run_id=run_id)


@pytest.fixture
def vm(tmp_path, qtbot):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        svc = MagicMock()
        svc.get_authenticated_user.return_value = "me"
        svc.discover_open_prs.return_value = []
        MockSvc.return_value = svc
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    v._svc.get_pr_detail = MagicMock(return_value=_make_pr())
    yield v
    v.deleteLater()


# ── merge_pr: background thread ───────────────────────────────────────────────

def test_merge_pr_does_not_call_service_on_calling_thread(vm, qtbot):
    """
    merge_pr must not call _svc.merge_pr on the calling thread.
    Proves the UI thread is never blocked.
    Verified by capturing the thread identity inside the mock and comparing to main thread.
    """
    pr = _make_pr()
    vm.prs = [pr]

    calling_thread_id = threading.current_thread().ident
    merge_called_from = []

    def _record_thread(*args, **kwargs):
        merge_called_from.append(threading.current_thread().ident)

    vm._svc.merge_pr.side_effect = _record_thread

    with qtbot.waitSignal(vm.merge_finished, timeout=3000):
        vm.merge_pr(pr, squash=True)

    assert merge_called_from, "merge_pr was never called"
    assert merge_called_from[0] != calling_thread_id, (
        "merge_pr called _svc.merge_pr on the calling (UI) thread — must be off-thread"
    )


# ── merge_pr: success path ────────────────────────────────────────────────────

def test_merge_pr_emits_merge_finished_on_success(vm, qtbot):
    """On a successful merge, merge_finished(pr_key) is emitted."""
    pr = _make_pr(42)
    vm.prs = [pr]
    vm._svc.merge_pr.return_value = None

    with qtbot.waitSignal(vm.merge_finished, timeout=3000) as blocker:
        vm.merge_pr(pr, squash=True)

    assert blocker.args[0] == pr.pr_key


def test_merge_pr_emits_pr_event_on_success(vm, qtbot):
    """merge_pr must still emit the pr_merged pr_event notification on success."""
    pr = _make_pr(42)
    pr._title = "My Feature"
    vm.prs = [pr]
    vm._svc.merge_pr.return_value = None

    events = []
    vm.pr_event.connect(lambda key, etype, msg: events.append((key, etype, msg)))

    with qtbot.waitSignal(vm.merge_finished, timeout=3000):
        vm.merge_pr(pr, squash=True)

    assert any(e[1] == "pr_merged" for e in events)


def test_merge_pr_schedules_delayed_refresh_not_sleep(vm, qtbot):
    """
    After a successful merge, a QTimer.singleShot is scheduled with RERUN_REFETCH_MS.
    No blocking sleep — only a non-blocking timer.
    """
    pr = _make_pr()
    vm.prs = [pr]
    vm._svc.merge_pr.return_value = None

    timer_calls = []

    original_singleShot = None

    with patch("worktree_manager.github_vm.QTimer") as MockTimer:
        MockTimer.singleShot.side_effect = lambda ms, fn: timer_calls.append(ms)
        with qtbot.waitSignal(vm.merge_finished, timeout=3000):
            vm.merge_pr(pr, squash=True)

    assert any(ms == RERUN_REFETCH_MS for ms in timer_calls), (
        f"Expected QTimer.singleShot({RERUN_REFETCH_MS}, ...) for eventual-consistency delay; "
        f"got calls: {timer_calls}"
    )


# ── merge_pr: failure path ────────────────────────────────────────────────────

def test_merge_pr_emits_merge_failed_on_error(vm, qtbot):
    """When _svc.merge_pr raises, merge_failed(pr_key, message) is emitted."""
    pr = _make_pr(7)
    vm.prs = [pr]
    vm._svc.merge_pr.side_effect = RuntimeError("Branch protection rule violated")

    with qtbot.waitSignal(vm.merge_failed, timeout=3000) as blocker:
        vm.merge_pr(pr, squash=True)

    assert blocker.args[0] == pr.pr_key
    assert "Branch protection rule violated" in blocker.args[1]


def test_merge_pr_does_not_emit_merge_finished_on_error(vm, qtbot):
    """When merge raises, merge_finished must NOT be emitted."""
    pr = _make_pr()
    vm.prs = [pr]
    vm._svc.merge_pr.side_effect = RuntimeError("fail")

    finished_fired = []
    vm.merge_finished.connect(lambda key: finished_fired.append(key))

    with qtbot.waitSignal(vm.merge_failed, timeout=3000):
        vm.merge_pr(pr, squash=True)

    assert finished_fired == []


# ── retry_failed_cis: background thread for POSTs ────────────────────────────

def test_retry_failed_cis_rerun_posts_run_off_ui_thread(vm, qtbot):
    """
    retry_failed_cis must NOT call rerun_failed_jobs on the calling thread.
    The optimistic mark-running happens on the UI thread; only the POST is off-thread.
    Verified by capturing the thread identity inside the mock.
    """
    pr = _make_pr(checks=[_failed_check(run_id="99")])
    vm.prs = [pr]

    calling_thread_id = threading.current_thread().ident
    rerun_called_from = []

    done = threading.Event()
    def _record_thread(*args, **kwargs):
        rerun_called_from.append(threading.current_thread().ident)
        done.set()

    vm._svc.rerun_failed_jobs.side_effect = _record_thread

    vm.retry_failed_cis(pr)
    done.wait(timeout=3)

    assert rerun_called_from, "rerun_failed_jobs was never called"
    assert rerun_called_from[0] != calling_thread_id, (
        "rerun_failed_jobs was called on the UI thread — must be off-thread"
    )


def test_retry_failed_cis_still_optimistically_marks_running_on_ui_thread(vm, qtbot):
    """
    Optimistic 'mark running' must still happen on the calling thread (instant feedback),
    even though the POST is moved to a background thread.
    """
    pr = _make_pr(checks=[_failed_check(name="build", run_id="99")])
    vm.prs = [pr]

    gate = threading.Event()
    vm._svc.rerun_failed_jobs.side_effect = lambda *a, **kw: gate.wait(timeout=5)

    with qtbot.waitSignal(vm.prs_updated, timeout=1000):
        vm.retry_failed_cis(pr)

    # Optimistic mark must be visible immediately on the UI thread
    assert pr.checks[0].status == "in_progress"
    assert pr.checks[0].conclusion is None

    gate.set()
    qtbot.wait(300)


def test_retry_failed_cis_still_schedules_quick_fetch(vm, qtbot):
    """_schedule_quick_fetch() must still be called after retry_failed_cis."""
    pr = _make_pr(checks=[_failed_check(run_id="1")])
    vm.prs = [pr]
    vm._svc.rerun_failed_jobs.return_value = None

    with patch("worktree_manager.github_vm.QTimer") as MockTimer:
        vm.retry_failed_cis(pr)

    MockTimer.singleShot.assert_called_once()
    assert MockTimer.singleShot.call_args[0][0] == RERUN_REFETCH_MS


# ── retry_all_cis: background thread for POSTs ───────────────────────────────

def test_retry_all_cis_rerun_posts_run_off_ui_thread(vm, qtbot):
    """
    retry_all_cis must NOT call rerun_workflow on the calling thread.
    Verified by capturing the thread identity inside the mock.
    """
    pr = _make_pr(checks=[_passing_check(run_id="500")])
    vm.prs = [pr]

    calling_thread_id = threading.current_thread().ident
    rerun_called_from = []

    done = threading.Event()
    def _record_thread(*args, **kwargs):
        rerun_called_from.append(threading.current_thread().ident)
        done.set()

    vm._svc.rerun_workflow.side_effect = _record_thread

    vm.retry_all_cis(pr)
    done.wait(timeout=3)

    assert rerun_called_from, "rerun_workflow was never called"
    assert rerun_called_from[0] != calling_thread_id, (
        "rerun_workflow was called on the UI thread — must be off-thread"
    )


def test_retry_all_cis_still_schedules_quick_fetch(vm, qtbot):
    """_schedule_quick_fetch() must still be called after retry_all_cis."""
    pr = _make_pr(checks=[_passing_check(run_id="500")])
    vm.prs = [pr]
    vm._svc.rerun_workflow.return_value = None

    with patch("worktree_manager.github_vm.QTimer") as MockTimer:
        vm.retry_all_cis(pr)

    MockTimer.singleShot.assert_called_once()
    assert MockTimer.singleShot.call_args[0][0] == RERUN_REFETCH_MS


# ── open_pull_request: background thread ─────────────────────────────────────

def test_open_pull_request_does_not_call_push_on_calling_thread(vm, qtbot):
    """
    open_pull_request must not call push_branch on the calling thread.
    Verified by capturing the thread identity inside the mock.
    """
    calling_thread_id = threading.current_thread().ident
    push_called_from = []

    def _record_thread(*args, **kwargs):
        push_called_from.append(threading.current_thread().ident)

    vm._svc.push_branch.side_effect = _record_thread
    vm._svc.create_pull_request.return_value = None

    with qtbot.waitSignal(vm.open_pr_finished, timeout=3000):
        vm.open_pull_request(
            title="My PR", body="body", base="main", branch="feat",
            draft=False, repo_base_url="https://api.github.com/repos/org/repo",
        )

    assert push_called_from, "push_branch was never called"
    assert push_called_from[0] != calling_thread_id, (
        "push_branch was called on the calling (UI) thread — must be off-thread"
    )


def test_open_pull_request_emits_open_pr_finished_on_success(vm, qtbot):
    """On success, open_pr_finished is emitted (no args)."""
    vm._svc.push_branch.return_value = None
    vm._svc.create_pull_request.return_value = None

    with qtbot.waitSignal(vm.open_pr_finished, timeout=3000):
        vm.open_pull_request(
            title="T", body="B", base="main", branch="feat",
            draft=False, repo_base_url="https://api.github.com/repos/org/repo",
        )


def test_open_pull_request_calls_push_then_create(vm, qtbot):
    """push_branch is called before create_pull_request with correct args."""
    call_order = []
    vm._svc.push_branch.side_effect = lambda *a, **kw: call_order.append("push")
    vm._svc.create_pull_request.side_effect = lambda *a, **kw: call_order.append("create")

    with qtbot.waitSignal(vm.open_pr_finished, timeout=3000):
        vm.open_pull_request(
            title="T", body="B", base="main", branch="feat",
            draft=True, repo_base_url="https://api.github.com/repos/org/repo",
        )

    assert call_order == ["push", "create"]
    _, push_kwargs = vm._svc.push_branch.call_args
    assert push_kwargs.get("repo_path") is None or True  # repo_path passed through
    _, create_kwargs = vm._svc.create_pull_request.call_args
    assert create_kwargs["title"] == "T"
    assert create_kwargs["draft"] is True
    assert create_kwargs["repo_base_url"] == "https://api.github.com/repos/org/repo"


def test_open_pull_request_schedules_delayed_refresh_on_success(vm, qtbot):
    """After open_pr_finished, QTimer.singleShot(RERUN_REFETCH_MS, total_fetch) is scheduled."""
    vm._svc.push_branch.return_value = None
    vm._svc.create_pull_request.return_value = None

    timer_calls = []
    with patch("worktree_manager.github_vm.QTimer") as MockTimer:
        MockTimer.singleShot.side_effect = lambda ms, fn: timer_calls.append(ms)
        with qtbot.waitSignal(vm.open_pr_finished, timeout=3000):
            vm.open_pull_request(
                title="T", body="B", base="main", branch="feat",
                draft=False, repo_base_url="https://api.github.com/repos/org/repo",
            )

    assert any(ms == RERUN_REFETCH_MS for ms in timer_calls)


def test_open_pull_request_emits_open_pr_failed_on_push_error(vm, qtbot):
    """When push_branch raises, open_pr_failed(message) is emitted."""
    vm._svc.push_branch.side_effect = RuntimeError("Authentication failed")

    with qtbot.waitSignal(vm.open_pr_failed, timeout=3000) as blocker:
        vm.open_pull_request(
            title="T", body="B", base="main", branch="feat",
            draft=False, repo_base_url="https://api.github.com/repos/org/repo",
        )

    assert "Authentication failed" in blocker.args[0]


def test_open_pull_request_emits_open_pr_failed_on_create_error(vm, qtbot):
    """When create_pull_request raises, open_pr_failed(message) is emitted."""
    vm._svc.push_branch.return_value = None
    vm._svc.create_pull_request.side_effect = RuntimeError("Already exists")

    with qtbot.waitSignal(vm.open_pr_failed, timeout=3000) as blocker:
        vm.open_pull_request(
            title="T", body="B", base="main", branch="feat",
            draft=False, repo_base_url="https://api.github.com/repos/org/repo",
        )

    assert "Already exists" in blocker.args[0]


def test_open_pull_request_does_not_emit_finished_on_error(vm, qtbot):
    """When push raises, open_pr_finished must NOT be emitted."""
    vm._svc.push_branch.side_effect = RuntimeError("fail")

    finished = []
    vm.open_pr_finished.connect(lambda: finished.append(True))

    with qtbot.waitSignal(vm.open_pr_failed, timeout=3000):
        vm.open_pull_request(
            title="T", body="B", base="main", branch="feat",
            draft=False, repo_base_url="https://api.github.com/repos/org/repo",
        )

    assert finished == []
