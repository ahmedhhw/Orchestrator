"""Tests for per-repo notification gating and ready_to_merge in GitHubViewModel."""
import pytest
from unittest.mock import patch
from worktree_manager.github_models import CICheck, PullRequest, Review, PRComment
from worktree_manager.github_vm import GitHubViewModel


def _make_pr(number=1, owner="org", repo="myrepo", title="My Work",
             checks=None, reviews=None, comments=None, mergeable=True):
    return PullRequest(
        number=number, title=title, body="",
        html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
        head_branch="feat", base_branch="main", state="open", draft=False,
        mergeable=mergeable,
        checks=checks or [], reviews=reviews or [], comments=comments or [],
        owner=owner, repo=repo,
    )


@pytest.fixture
def vm(tmp_path, qtbot):
    from worktree_manager.config_store import ConfigStore
    store = ConfigStore(path=tmp_path / "config.json")
    store.save_github_token("ghp_test")
    with patch("worktree_manager.github_vm.GitHubService"):
        v = GitHubViewModel(store=store)
        v._total_timer.stop()
        v._quick_timer.stop()
    return v


class TestNotificationGating:
    def test_emit_suppressed_when_repo_toggle_is_off(self, vm, qtbot):
        vm._store.set_repo_notification_pref("org/myrepo", "ci_failed", False)

        pr_before = _make_pr(checks=[CICheck("build", "in_progress", None)])
        pr_after = _make_pr(checks=[CICheck("build", "completed", "failure")])
        vm._emit_pr_events([pr_before])

        events = []
        vm.pr_event.connect(lambda key, evt, msg: events.append(evt))
        vm._emit_pr_events([pr_after])

        assert "ci_failed" not in events

    def test_emit_fires_when_repo_toggle_is_on(self, vm, qtbot):
        # toggle is on by default — no explicit set needed
        pr_before = _make_pr(checks=[CICheck("build", "in_progress", None)])
        pr_after = _make_pr(checks=[CICheck("build", "completed", "failure")])
        vm._emit_pr_events([pr_before])

        events = []
        vm.pr_event.connect(lambda key, evt, msg: events.append(evt))
        vm._emit_pr_events([pr_after])

        assert "ci_failed" in events

    def test_review_approved_suppressed_when_review_toggle_off(self, vm, qtbot):
        vm._store.set_repo_notification_pref("org/myrepo", "review", False)

        pr_before = _make_pr(reviews=[])
        pr_after = _make_pr(reviews=[Review(author="alice", state="APPROVED")])
        vm._emit_pr_events([pr_before])

        events = []
        vm.pr_event.connect(lambda key, evt, msg: events.append(evt))
        vm._emit_pr_events([pr_after])

        assert "review_approved" not in events

    def test_review_changes_requested_suppressed_when_review_toggle_off(self, vm, qtbot):
        vm._store.set_repo_notification_pref("org/myrepo", "review", False)

        pr_before = _make_pr(reviews=[])
        pr_after = _make_pr(reviews=[Review(author="bob", state="CHANGES_REQUESTED")])
        vm._emit_pr_events([pr_before])

        events = []
        vm.pr_event.connect(lambda key, evt, msg: events.append(evt))
        vm._emit_pr_events([pr_after])

        assert "review_changes_requested" not in events


class TestReadyToMerge:
    def test_ready_to_merge_fires_on_not_ready_to_ready_transition(self, vm, qtbot):
        pr_before = _make_pr(mergeable=False)
        pr_after = _make_pr(mergeable=True)
        vm._emit_pr_events([pr_before])

        events = []
        vm.pr_event.connect(lambda key, evt, msg: events.append(evt))
        vm._emit_pr_events([pr_after])

        assert "ready_to_merge" in events

    def test_ready_to_merge_fires_only_once(self, vm, qtbot):
        pr_not_ready = _make_pr(mergeable=False)
        pr_ready = _make_pr(mergeable=True)
        vm._emit_pr_events([pr_not_ready])

        events = []
        vm.pr_event.connect(lambda key, evt, msg: events.append(evt))
        vm._emit_pr_events([pr_ready])   # transition: fires
        vm._emit_pr_events([pr_ready])   # stays ready: should not fire again

        assert events.count("ready_to_merge") == 1

    def test_ready_to_merge_suppressed_when_toggle_off(self, vm, qtbot):
        vm._store.set_repo_notification_pref("org/myrepo", "ready_to_merge", False)

        pr_before = _make_pr(mergeable=False)
        pr_after = _make_pr(mergeable=True)
        vm._emit_pr_events([pr_before])

        events = []
        vm.pr_event.connect(lambda key, evt, msg: events.append(evt))
        vm._emit_pr_events([pr_after])

        assert "ready_to_merge" not in events


class TestCiDedupWithMuted:
    def test_muted_failure_repo_still_notifies_on_genuine_pass(self, vm, qtbot):
        """Muting a failing check means the muted-recomputed CI status is 'passed'.
        When a genuine pass replaces a real failure, notification must fire.
        This test verifies the dedup uses the muted-recomputed status."""
        vm._store.set_repo_muted_checks("org/myrepo", ["flaky"])

        # Start: one real failure + one muted failure → muted-ci = "failed"
        pr_failing = _make_pr(checks=[
            CICheck("real-build", "completed", "failure"),
            CICheck("flaky", "completed", "failure"),
        ])
        vm._emit_pr_events([pr_failing])  # seed: muted-ci = "failed"

        # Now: real failure is fixed, flaky still muted → muted-ci = "passed"
        pr_passed = _make_pr(checks=[
            CICheck("real-build", "completed", "success"),
            CICheck("flaky", "completed", "failure"),
        ])
        events = []
        vm.pr_event.connect(lambda key, evt, msg: events.append(evt))
        vm._emit_pr_events([pr_passed])

        assert "ci_passed" in events
