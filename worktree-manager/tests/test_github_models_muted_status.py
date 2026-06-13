"""Tests for ci_status(muted=) and ci_status_summary() on PullRequest."""
from worktree_manager.github_models import CICheck, PullRequest


def _pr(**kwargs) -> PullRequest:
    defaults = dict(
        number=1, title="T", body="", html_url="https://github.com/org/repo/pull/1",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
    )
    defaults.update(kwargs)
    return PullRequest(**defaults)


class TestCiStatusMuted:
    def test_muted_failing_check_no_longer_yields_failed(self):
        pr = _pr(checks=[
            CICheck("flaky-lint", "completed", "failure"),
            CICheck("build", "completed", "success"),
        ])
        assert pr.ci_status(muted={"flaky-lint"}) == "passed"

    def test_ci_status_summary_reports_ignored_count(self):
        pr = _pr(checks=[
            CICheck("flaky-lint", "completed", "failure"),
            CICheck("build", "completed", "success"),
        ])
        status, ignored = pr.ci_status_summary(muted={"flaky-lint"})
        assert status == "passed"
        assert ignored == 1

    def test_real_failure_still_yields_failed_with_another_muted(self):
        pr = _pr(checks=[
            CICheck("flaky-lint", "completed", "failure"),  # muted
            CICheck("build", "completed", "failure"),       # real failure
        ])
        assert pr.ci_status(muted={"flaky-lint"}) == "failed"

    def test_muting_only_check_yields_unknown(self):
        pr = _pr(checks=[CICheck("solo", "completed", "failure")])
        assert pr.ci_status(muted={"solo"}) == "unknown"
