"""Tests for group_and_filter in github_search."""
import pytest
from worktree_manager.github_models import PullRequest
from worktree_manager.github_search import group_and_filter, RepoGroup


def _pr(number: int, title: str, owner: str, repo: str) -> PullRequest:
    return PullRequest(
        number=number,
        title=title,
        body="",
        html_url=f"https://github.com/{owner}/{repo}/pull/{number}",
        head_branch="feat",
        base_branch="main",
        state="open",
        draft=False,
        mergeable=True,
        owner=owner,
        repo=repo,
    )


class TestGroupAndFilter:
    def test_groups_prs_by_owner_repo(self):
        pr1 = _pr(1, "Alpha", "org", "repo-a")
        pr2 = _pr(2, "Beta", "org", "repo-b")
        pr3 = _pr(3, "Gamma", "org", "repo-a")

        groups = group_and_filter([pr1, pr2, pr3], needle="")

        repos = [g.repo for g in groups]
        assert "org/repo-a" in repos
        assert "org/repo-b" in repos
        group_a = next(g for g in groups if g.repo == "org/repo-a")
        assert len(group_a.prs) == 2
        assert len(next(g for g in groups if g.repo == "org/repo-b").prs) == 1

    def test_empty_needle_groups_in_repo_name_order(self):
        pr_z = _pr(1, "Z", "org", "z-repo")
        pr_a = _pr(2, "A", "org", "a-repo")
        pr_m = _pr(3, "M", "org", "m-repo")

        groups = group_and_filter([pr_z, pr_a, pr_m], needle="")

        assert [g.repo for g in groups] == ["org/a-repo", "org/m-repo", "org/z-repo"]

    def test_empty_needle_prs_within_group_preserve_original_order(self):
        pr3 = _pr(3, "C", "org", "repo")
        pr1 = _pr(1, "A", "org", "repo")
        pr2 = _pr(2, "B", "org", "repo")

        groups = group_and_filter([pr3, pr1, pr2], needle="")

        assert groups[0].prs == [pr3, pr1, pr2]

    def test_search_needle_drops_nonmatching_prs_and_removes_empty_groups(self):
        pr_match = _pr(1, "login page", "org", "frontend")
        pr_nomatch = _pr(2, "update readme", "org", "docs")

        groups = group_and_filter([pr_match, pr_nomatch], needle="login")

        assert len(groups) == 1
        assert groups[0].repo == "org/frontend"
        assert groups[0].prs == [pr_match]

    def test_groups_ordered_by_best_member_score(self):
        # "login" matches "login form" much better than "refactor login helper"
        pr_high = _pr(1, "login form", "org", "frontend")    # best score in its group
        pr_low = _pr(2, "refactor login helper", "org", "backend")  # lower score

        groups = group_and_filter([pr_low, pr_high], needle="login")

        assert groups[0].repo == "org/frontend"
        assert groups[1].repo == "org/backend"

    def test_prs_within_group_ordered_by_score_desc(self):
        # "login" matches "login" better than "refactor login thing"
        pr_best = _pr(1, "login", "org", "repo")
        pr_worst = _pr(2, "refactor login thing", "org", "repo")

        groups = group_and_filter([pr_worst, pr_best], needle="login")

        assert groups[0].prs[0] is pr_best

    def test_group_count_reflects_post_filter_visible_prs(self):
        pr_match1 = _pr(1, "login page", "org", "repo")
        pr_match2 = _pr(2, "login form", "org", "repo")
        pr_nomatch = _pr(3, "update readme", "org", "repo")

        groups = group_and_filter([pr_match1, pr_match2, pr_nomatch], needle="login")

        assert groups[0].count == 2
