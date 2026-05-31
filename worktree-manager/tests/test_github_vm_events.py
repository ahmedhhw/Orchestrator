import pytest
from unittest.mock import MagicMock, patch
from worktree_manager.github_models import PullRequest, CICheck, Review, PRComment
from worktree_manager.github_vm import GitHubViewModel, TokenState


def _make_pr(number=1, head="feat", base="main", checks=None, reviews=None, comments=None):
    return PullRequest(
        number=number, title="My Work", body="", html_url=f"http://x/{number}",
        head_branch=head, base_branch=base, state="open", draft=False, mergeable=True,
        checks=checks or [], reviews=reviews or [], comments=comments or [],
    )


@pytest.fixture
def vm(tmp_path):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
    return v


def test_ci_failed_event_emitted_when_checks_transition_to_failed(vm, qtbot):
    pr_before = _make_pr(1, checks=[CICheck("build", "in_progress", None)])
    pr_after  = _make_pr(1, checks=[CICheck("build", "completed", "failure")])
    vm._pr_snapshots = {1: pr_before}

    events = []
    vm.pr_event.connect(lambda num, evt, msg: events.append((num, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "ci_failed" for e in events)
    assert any("My Work" in e[2] for e in events)


def test_ci_passed_event_emitted_when_all_checks_pass(vm, qtbot):
    pr_before = _make_pr(1, checks=[CICheck("build", "in_progress", None)])
    pr_after  = _make_pr(1, checks=[CICheck("build", "completed", "success")])
    vm._pr_snapshots = {1: pr_before}

    events = []
    vm.pr_event.connect(lambda num, evt, msg: events.append((num, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "ci_passed" for e in events)


def test_new_comment_event_emitted_when_comment_count_grows(vm, qtbot):
    pr_before = _make_pr(1, comments=[PRComment(id=1, author="alice", body="hi", created_at="2024-01-01")])
    pr_after  = _make_pr(1, comments=[
        PRComment(id=1, author="alice", body="hi", created_at="2024-01-01"),
        PRComment(id=2, author="bob",   body="yo", created_at="2024-01-02"),
    ])
    vm._pr_snapshots = {1: pr_before}

    events = []
    vm.pr_event.connect(lambda num, evt, msg: events.append((num, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "new_comment" for e in events)
    assert any("bob" in e[2] for e in events)


def test_review_approved_event_emitted(vm, qtbot):
    pr_before = _make_pr(1, reviews=[])
    pr_after  = _make_pr(1, reviews=[Review(author="alice", state="APPROVED")])
    vm._pr_snapshots = {1: pr_before}

    events = []
    vm.pr_event.connect(lambda num, evt, msg: events.append((num, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "review_approved" for e in events)
    assert any("alice" in e[2] for e in events)


def test_review_changes_requested_event_emitted(vm, qtbot):
    pr_before = _make_pr(1, reviews=[])
    pr_after  = _make_pr(1, reviews=[Review(author="bob", state="CHANGES_REQUESTED")])
    vm._pr_snapshots = {1: pr_before}

    events = []
    vm.pr_event.connect(lambda num, evt, msg: events.append((num, evt, msg)))
    vm._emit_pr_events([pr_after])

    assert any(e[1] == "review_changes_requested" for e in events)


def test_no_events_when_nothing_changed(vm, qtbot):
    pr = _make_pr(1, checks=[CICheck("build", "completed", "success")])
    vm._pr_snapshots = {1: pr}

    events = []
    vm.pr_event.connect(lambda num, evt, msg: events.append((num, evt, msg)))
    vm._emit_pr_events([pr])

    assert events == []


def test_new_pr_does_not_emit_events_on_first_seen(vm, qtbot):
    pr = _make_pr(1, checks=[CICheck("build", "completed", "failure")])
    vm._pr_snapshots = {}

    events = []
    vm.pr_event.connect(lambda num, evt, msg: events.append((num, evt, msg)))
    vm._emit_pr_events([pr])

    assert events == []


def test_snapshots_updated_after_emit(vm, qtbot):
    pr = _make_pr(1, checks=[CICheck("build", "completed", "success")])
    vm._pr_snapshots = {}
    vm._emit_pr_events([pr])
    assert 1 in vm._pr_snapshots
