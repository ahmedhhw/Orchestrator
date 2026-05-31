import pytest
from worktree_manager.github_models import PullRequest, CICheck, Review


def _make_pr(checks=None, reviews=None, mergeable=True):
    return PullRequest(
        number=1, title="My Work", body="",
        html_url="https://github.com/o/r/pull/1",
        head_branch="feat", base_branch="main",
        state="open", draft=False,
        mergeable=mergeable,
        checks=checks or [],
        reviews=reviews or [],
    )


def test_ready_to_merge_when_all_checks_pass_and_approved():
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    assert pr.is_ready_to_merge() is True


def test_ready_when_checks_failed_but_mergeable_and_approved():
    pr = _make_pr(
        checks=[CICheck("build", "completed", "failure")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    assert pr.is_ready_to_merge() is True


def test_ready_when_checks_running_but_mergeable_and_approved():
    pr = _make_pr(
        checks=[CICheck("build", "in_progress", None)],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    assert pr.is_ready_to_merge() is True


def test_ready_when_no_approved_review_but_mergeable():
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "COMMENTED")],
        mergeable=True,
    )
    assert pr.is_ready_to_merge() is True


def test_ready_when_no_reviews_but_mergeable():
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[],
        mergeable=True,
    )
    assert pr.is_ready_to_merge() is True


def test_not_ready_when_not_mergeable():
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=False,
    )
    assert pr.is_ready_to_merge() is False


def test_not_ready_when_mergeable_is_none():
    pr = _make_pr(
        checks=[CICheck("build", "completed", "success")],
        reviews=[Review("alice", "APPROVED")],
        mergeable=None,
    )
    assert not pr.is_ready_to_merge()


def test_ready_when_no_checks_but_mergeable_and_approved():
    pr = _make_pr(
        checks=[],
        reviews=[Review("alice", "APPROVED")],
        mergeable=True,
    )
    assert pr.is_ready_to_merge() is True
