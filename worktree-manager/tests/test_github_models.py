from worktree_manager.github_models import CICheck, PRComment, PullRequest, Review


def _pr(**kwargs) -> PullRequest:
    defaults = dict(
        number=1, title="T", body="", html_url="http://x", head_branch="feat",
        base_branch="main", state="open", draft=False, mergeable=True,
    )
    defaults.update(kwargs)
    return PullRequest(**defaults)


class TestCiStatus:
    def test_no_checks_is_unknown(self):
        assert _pr().ci_status() == "unknown"

    def test_all_success_is_passed(self):
        pr = _pr(checks=[CICheck("build", "completed", "success")])
        assert pr.ci_status() == "passed"

    def test_any_failure_is_failed(self):
        pr = _pr(checks=[
            CICheck("build", "completed", "failure"),
            CICheck("lint", "completed", "success"),
        ])
        assert pr.ci_status() == "failed"

    def test_any_in_progress_is_running(self):
        pr = _pr(checks=[
            CICheck("build", "in_progress", None),
            CICheck("lint", "completed", "success"),
        ])
        assert pr.ci_status() == "running"

    def test_failure_takes_priority_over_running(self):
        pr = _pr(checks=[
            CICheck("build", "completed", "failure"),
            CICheck("lint", "in_progress", None),
        ])
        assert pr.ci_status() == "failed"


class TestIsReadyToMerge:
    def test_ready_when_all_pass_and_approved(self):
        pr = _pr(
            checks=[CICheck("build", "completed", "success")],
            reviews=[Review("alice", "APPROVED")],
            mergeable=True,
        )
        assert pr.is_ready_to_merge() is True

    def test_ready_when_checks_running_but_mergeable_and_approved(self):
        pr = _pr(
            checks=[CICheck("build", "in_progress", None)],
            reviews=[Review("alice", "APPROVED")],
            mergeable=True,
        )
        assert pr.is_ready_to_merge() is True

    def test_ready_without_approval_when_mergeable(self):
        pr = _pr(
            checks=[CICheck("build", "completed", "success")],
            reviews=[],
            mergeable=True,
        )
        assert pr.is_ready_to_merge() is True

    def test_not_ready_when_not_mergeable(self):
        pr = _pr(
            checks=[CICheck("build", "completed", "success")],
            reviews=[Review("alice", "APPROVED")],
            mergeable=False,
        )
        assert pr.is_ready_to_merge() is False


class TestMergeability:
    def test_clean_is_mergeable(self):
        assert _pr(mergeable=True, mergeable_state="clean").mergeability() == "mergeable"

    def test_unstable_is_mergeable(self):
        assert _pr(mergeable=True, mergeable_state="unstable").mergeability() == "mergeable"

    def test_dirty_is_conflicts(self):
        assert _pr(mergeable=False, mergeable_state="dirty").mergeability() == "conflicts"

    def test_behind_is_behind(self):
        assert _pr(mergeable=False, mergeable_state="behind").mergeability() == "behind"

    def test_blocked_is_blocked(self):
        assert _pr(mergeable=False, mergeable_state="blocked").mergeability() == "blocked"

    def test_unknown_state_with_none_is_checking(self):
        assert _pr(mergeable=None, mergeable_state="unknown").mergeability() == "checking"

    def test_empty_state_with_none_is_checking(self):
        assert _pr(mergeable=None, mergeable_state="").mergeability() == "checking"

    def test_mergeable_state_defaults_to_empty_string(self):
        assert _pr().mergeable_state == ""

    def test_is_ready_to_merge_unchanged_depends_only_on_mergeable(self):
        assert _pr(mergeable=True, mergeable_state="dirty").is_ready_to_merge() is True
        assert _pr(mergeable=False, mergeable_state="clean").is_ready_to_merge() is False


class TestPRCommentSeen:
    def test_seen_defaults_to_false(self):
        c = PRComment(id=1, author="alice", body="hi", created_at="2024-01-01T00:00:00Z")
        assert c.seen is False

    def test_seen_can_be_set_true(self):
        c = PRComment(id=1, author="alice", body="hi", created_at="2024-01-01T00:00:00Z", seen=True)
        assert c.seen is True
