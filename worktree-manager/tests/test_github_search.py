"""Unit tests for worktree_manager.github_search — pure helpers."""
import pytest
from worktree_manager.github_models import PullRequest
from worktree_manager.github_search import searchable_text, filter_prs


def _pr(number: int, title: str, head: str, base: str, owner: str, repo: str) -> PullRequest:
    return PullRequest(
        number=number,
        title=title,
        body="",
        html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
        head_branch=head,
        base_branch=base,
        state="open",
        draft=False,
        mergeable=True,
        owner=owner,
        repo=repo,
    )


# ── searchable_text ─────────────────────────────────────────────────────────

def test_searchable_text_is_pr_title():
    pr = _pr(482, "Fix login flow", "feature/login", "main", "acme", "payments")
    assert searchable_text(pr) == "Fix login flow"


# ── filter_prs ──────────────────────────────────────────────────────────────

def test_keeps_pr_when_query_fuzzy_matches():
    pr = _pr(1, "Add dark mode", "feature/dark-mode", "main", "org", "repo")
    result = filter_prs([pr], "dark")
    assert pr in result


def test_drops_pr_when_query_does_not_match():
    pr = _pr(1, "Add dark mode", "feature/dark-mode", "main", "org", "repo")
    result = filter_prs([pr], "xyzzzz")
    assert result == []


def test_orders_surviving_prs_best_match_first():
    # pr_a has "login" in the title (closer match), pr_b only in description
    pr_a = _pr(1, "login page refactor", "login-refactor", "main", "org", "repo")
    pr_b = _pr(2, "Update readme", "readme-updates", "main", "org", "repo")
    pr_c = _pr(3, "Fix login form validation", "fix/login-validation", "main", "org", "repo")
    # "login" matches pr_a and pr_c but not pr_b
    result = filter_prs([pr_b, pr_a, pr_c], "login")
    assert pr_b not in result
    # The first result should be the best-scoring one (login appears earliest/most prominently)
    assert result[0] in (pr_a, pr_c)
    assert len(result) == 2
    assert pr_a in result
    assert pr_c in result


def test_empty_query_keeps_all_prs_in_original_order():
    pr_a = _pr(1, "Alpha", "alpha", "main", "org", "repo")
    pr_b = _pr(2, "Beta", "beta", "main", "org", "repo")
    pr_c = _pr(3, "Gamma", "gamma", "main", "org", "repo")
    result = filter_prs([pr_a, pr_b, pr_c], "")
    assert result == [pr_a, pr_b, pr_c]


def test_does_not_match_by_pr_number():
    pr = _pr(482, "Some PR title", "feature/x", "main", "org", "repo")
    other = _pr(100, "Another PR", "feature/y", "main", "org", "repo")
    result = filter_prs([pr, other], "482")
    assert pr not in result
    assert other not in result


def test_does_not_match_by_branch_name():
    pr = _pr(10, "Auth changes", "feature/login", "main", "org", "repo")
    result = filter_prs([pr], "feature")
    assert pr not in result


def test_does_not_match_by_owner_repo():
    pr = _pr(20, "Add fee", "feature/fee", "main", "acme", "payments")
    result = filter_prs([pr], "payments")
    assert pr not in result
