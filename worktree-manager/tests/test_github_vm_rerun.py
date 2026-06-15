"""ViewModel orchestration tests for retry_failed_cis and retry_all_cis."""
import pytest
from unittest.mock import MagicMock, patch, call
from worktree_manager.github_models import CICheck, PullRequest
from worktree_manager.github_vm import GitHubViewModel


def _make_store(tmp_path):
    from worktree_manager.config_store import ConfigStore
    s = ConfigStore(path=tmp_path / "config.json")
    s.save_github_token("ghp_test")
    return s


def _make_pr(number=1, checks=None):
    return PullRequest(
        number=number, title=f"PR {number}", body="",
        html_url=f"https://github.com/org/repo/pull/{number}",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
        checks=checks or [],
    )


def _failed_check(name, run_id=None, suite_id="suite-1"):
    return CICheck(
        name=name, status="completed", conclusion="failure",
        check_suite_id=suite_id, run_id=run_id,
    )


def _passing_check(name, run_id=None, suite_id="suite-1"):
    return CICheck(
        name=name, status="completed", conclusion="success",
        check_suite_id=suite_id, run_id=run_id,
    )


@pytest.fixture
def vm(tmp_path, qtbot):
    store = _make_store(tmp_path)
    with patch("worktree_manager.github_vm.GitHubService") as MockSvc:
        MockSvc.return_value = MagicMock()
        v = GitHubViewModel(store=store)
    yield v
    v.deleteLater()


# ── retry_failed_cis ─────────────────────────────────────────────────────────

def test_retry_failed_cis_calls_rerun_failed_jobs_for_each_distinct_run_id(vm, qtbot):
    pr = _make_pr(checks=[
        _failed_check("a", run_id="99"),
        _failed_check("b", run_id="99"),   # same run, collapsed
        _failed_check("c", run_id="100"),
    ])
    vm._svc = MagicMock()
    vm.retry_failed_cis(pr)
    calls = vm._svc.rerun_failed_jobs.call_args_list
    assert len(calls) == 2
    called_ids = {c[0][0] for c in calls}
    assert called_ids == {"99", "100"}


def test_retry_failed_cis_marks_failed_actions_checks_as_running(vm, qtbot):
    pr = _make_pr(checks=[
        _failed_check("a", run_id="99"),
        _passing_check("b", run_id="100"),
    ])
    vm._svc = MagicMock()
    vm.prs = [pr]
    with qtbot.waitSignal(vm.prs_updated, timeout=1000):
        vm.retry_failed_cis(pr)
    # only the failed+has-run-id check is flipped
    check_a = pr.checks[0]
    check_b = pr.checks[1]
    assert check_a.status == "in_progress"
    assert check_a.conclusion is None
    # passing check untouched
    assert check_b.conclusion == "success"


def test_retry_failed_cis_emits_prs_updated(vm, qtbot):
    pr = _make_pr(checks=[_failed_check("a", run_id="1")])
    vm._svc = MagicMock()
    with qtbot.waitSignal(vm.prs_updated, timeout=1000):
        vm.retry_failed_cis(pr)


def test_retry_failed_cis_returns_note_when_some_checks_are_not_rerunnable(vm):
    pr = _make_pr(checks=[
        _failed_check("a", run_id="99"),       # rerunnable
        _failed_check("b", run_id=None),        # not rerunnable
        _failed_check("c", run_id=None),        # not rerunnable
    ])
    vm._svc = MagicMock()
    note = vm.retry_failed_cis(pr)
    assert "2" in note
    assert "non-Actions" in note or "can't" in note


def test_retry_failed_cis_returns_empty_string_when_all_rerunnable(vm):
    pr = _make_pr(checks=[_failed_check("a", run_id="99")])
    vm._svc = MagicMock()
    note = vm.retry_failed_cis(pr)
    assert note == ""


def test_retry_failed_cis_schedules_quick_fetch_after_configured_delay(vm, qtbot):
    pr = _make_pr(checks=[_failed_check("a", run_id="1")])
    vm._svc = MagicMock()
    with patch("worktree_manager.github_vm.QTimer") as MockTimer:
        vm.retry_failed_cis(pr)
    MockTimer.singleShot.assert_called_once()
    delay_arg = MockTimer.singleShot.call_args[0][0]
    from worktree_manager.github_vm import RERUN_REFETCH_MS
    assert delay_arg == RERUN_REFETCH_MS


def test_retry_failed_cis_emits_pr_event_for_toast(vm, qtbot):
    pr = _make_pr(checks=[_failed_check("a", run_id="1")])
    vm._svc = MagicMock()
    events = []
    vm.pr_event.connect(lambda pk, etype, msg: events.append((pk, etype, msg)))
    vm.retry_failed_cis(pr)
    assert any(e[1] == "ci_rerun" for e in events)
    assert any(str(pr.number) in e[2] for e in events)


# ── retry_all_cis ────────────────────────────────────────────────────────────

def test_retry_all_cis_calls_rerun_all_checks_with_suite_id(vm, qtbot):
    pr = _make_pr(checks=[
        _passing_check("a", suite_id="suite-42"),
        _failed_check("b", run_id="1", suite_id="suite-42"),
    ])
    vm._svc = MagicMock()
    vm.retry_all_cis(pr)
    vm._svc.rerun_all_checks.assert_called_once_with("suite-42", pr)


def test_retry_all_cis_marks_all_checks_as_running(vm, qtbot):
    pr = _make_pr(checks=[
        _passing_check("a", suite_id="suite-1"),
        _failed_check("b", run_id="1", suite_id="suite-1"),
    ])
    vm._svc = MagicMock()
    with qtbot.waitSignal(vm.prs_updated, timeout=1000):
        vm.retry_all_cis(pr)
    for c in pr.checks:
        assert c.status == "in_progress"
        assert c.conclusion is None
