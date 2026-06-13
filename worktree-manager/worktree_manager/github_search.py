"""Pure helpers for fuzzy-filtering PullRequest lists in the GitHub panel."""
from __future__ import annotations

from worktree_manager.spotlight.fuzzy import fuzzy_score


def searchable_text(pr) -> str:
    return pr.title


def filter_prs(prs, needle: str):
    """Return the subset of *prs* that fuzzy-match *needle*, ordered best-first.

    An empty needle returns all PRs in their original order.
    """
    if not needle:
        return list(prs)

    scored: list[tuple[int, int, object]] = []
    for idx, pr in enumerate(prs):
        score = fuzzy_score(needle, searchable_text(pr))
        if score is not None:
            scored.append((score, idx, pr))

    scored.sort(key=lambda t: (-t[0], t[1]))
    return [pr for _, _, pr in scored]
