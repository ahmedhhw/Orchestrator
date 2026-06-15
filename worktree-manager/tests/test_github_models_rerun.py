"""Tests for run_id field on CICheck and pure PR planning helpers on PullRequest."""
import pytest
from worktree_manager.github_models import CICheck, PullRequest
from worktree_manager.github_service import GitHubService


def _make_pr(**kwargs):
    defaults = dict(
        number=1, title="T", body="", html_url="https://github.com/org/repo/pull/1",
        head_branch="feat", base_branch="main", state="open", draft=False, mergeable=True,
    )
    defaults.update(kwargs)
    return PullRequest(**defaults)


# ── _parse_run_id ──────────────────────────────────────────────────────────────

def test_parse_run_id_from_actions_details_url():
    url = "https://github.com/org/repo/runs/456/job/789"
    # The service parses the api actions URL pattern
    result = GitHubService._parse_run_id(
        "https://api.github.com/repos/org/repo/actions/runs/123/jobs/456"
    )
    assert result == "123"


def test_parse_run_id_returns_none_for_non_actions_url():
    assert GitHubService._parse_run_id("https://example.com/check/42") is None


def test_parse_run_id_returns_none_for_empty_string():
    assert GitHubService._parse_run_id("") is None


# ── CICheck.run_id field ───────────────────────────────────────────────────────

def test_cicheck_carries_parsed_run_id():
    details_url = "https://api.github.com/repos/org/repo/actions/runs/99/jobs/1"
    check = CICheck(
        name="ci",
        status="completed",
        conclusion="failure",
        check_suite_id="suite-1",
        run_id=GitHubService._parse_run_id(details_url),
    )
    assert check.run_id == "99"


def test_cicheck_run_id_defaults_to_none():
    check = CICheck(name="ci", status="completed", conclusion="success")
    assert check.run_id is None


# ── PullRequest.failed_actions_run_ids ────────────────────────────────────────

def test_failed_actions_run_ids_returns_distinct_failed_run_ids():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="failure", run_id="99"),
        CICheck(name="b", status="completed", conclusion="failure", run_id="99"),  # same run
        CICheck(name="c", status="completed", conclusion="failure", run_id="100"),
    ]
    assert pr.failed_actions_run_ids() == ["99", "100"]


def test_failed_actions_run_ids_excludes_passing_checks():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="success", run_id="99"),
        CICheck(name="b", status="completed", conclusion="failure", run_id="100"),
    ]
    assert pr.failed_actions_run_ids() == ["100"]


def test_failed_actions_run_ids_ignores_failed_checks_without_run_id():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="failure", run_id=None),
        CICheck(name="b", status="completed", conclusion="failure", run_id="42"),
    ]
    result = pr.failed_actions_run_ids()
    assert None not in result
    assert result == ["42"]


# ── PullRequest.all_actions_run_ids ───────────────────────────────────────────

def test_all_actions_run_ids_returns_distinct_run_ids_across_all_checks():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="success", run_id="99"),
        CICheck(name="b", status="completed", conclusion="failure", run_id="99"),  # same run
        CICheck(name="c", status="completed", conclusion="success", run_id="100"),
    ]
    assert pr.all_actions_run_ids() == ["99", "100"]


def test_all_actions_run_ids_ignores_checks_without_run_id():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="success", run_id=None),
        CICheck(name="b", status="completed", conclusion="success", run_id="7"),
    ]
    assert pr.all_actions_run_ids() == ["7"]


def test_all_actions_run_ids_empty_when_no_actions_checks():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="failure", run_id=None),
    ]
    assert pr.all_actions_run_ids() == []


# ── PullRequest.non_rerunnable_failed_count ───────────────────────────────────

def test_non_rerunnable_failed_count_counts_failed_without_run_id():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="failure", run_id=None),
        CICheck(name="b", status="completed", conclusion="failure", run_id=None),
        CICheck(name="c", status="completed", conclusion="failure", run_id="99"),
    ]
    assert pr.non_rerunnable_failed_count() == 2


def test_non_rerunnable_failed_count_zero_when_all_have_run_ids():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="failure", run_id="1"),
    ]
    assert pr.non_rerunnable_failed_count() == 0


# ── PullRequest.check_suite_id_for_all ───────────────────────────────────────

def test_check_suite_id_for_all_returns_first_available():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="success", check_suite_id="suite-7"),
        CICheck(name="b", status="completed", conclusion="failure", check_suite_id="suite-8"),
    ]
    assert pr.check_suite_id_for_all() == "suite-7"


def test_check_suite_id_for_all_returns_none_when_no_checks():
    pr = _make_pr()
    pr.checks = []
    assert pr.check_suite_id_for_all() is None


def test_check_suite_id_for_all_returns_none_when_no_suite_ids():
    pr = _make_pr()
    pr.checks = [
        CICheck(name="a", status="completed", conclusion="success", check_suite_id=None),
    ]
    assert pr.check_suite_id_for_all() is None
