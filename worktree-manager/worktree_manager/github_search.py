"""Pure helpers for fuzzy-filtering PullRequest lists in the GitHub panel."""
from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass
class RepoGroup:
    repo: str
    count: int
    collapsed: bool
    prs: list = field(default_factory=list)


def group_and_filter(prs, needle: str, collapsed_repos=frozenset()) -> list[RepoGroup]:
    """Group *prs* by owner/repo, applying optional fuzzy filtering by *needle*.

    Empty needle: preserves original PR order within each group, groups sorted
    by repo name ascending.
    Non-empty needle: scores each PR; drops non-matching PRs and empty groups;
    within-group PRs ordered by score desc; groups ordered by best-member score
    desc (tie-break: repo name asc).
    """
    if not needle:
        # Preserve original pr_key ordering within groups
        groups_map: dict[str, list] = {}
        for pr in prs:
            key = f"{pr.owner}/{pr.repo}"
            groups_map.setdefault(key, []).append(pr)
        result = []
        for repo_key in sorted(groups_map):
            group_prs = groups_map[repo_key]
            result.append(RepoGroup(
                repo=repo_key,
                count=len(group_prs),
                collapsed=repo_key in collapsed_repos,
                prs=group_prs,
            ))
        return result

    # Fuzzy path: score each PR
    scored: list[tuple[int, int, object]] = []
    for idx, pr in enumerate(prs):
        score = fuzzy_score(needle, searchable_text(pr))
        if score is not None:
            scored.append((score, idx, pr))

    # Group survivors
    groups_map: dict[str, list[tuple[int, object]]] = {}
    for score, _idx, pr in scored:
        key = f"{pr.owner}/{pr.repo}"
        groups_map.setdefault(key, []).append((score, pr))

    result = []
    for repo_key, members in groups_map.items():
        members.sort(key=lambda t: -t[0])
        best_score = members[0][0]
        group_prs = [pr for _, pr in members]
        result.append((best_score, repo_key, RepoGroup(
            repo=repo_key,
            count=len(group_prs),
            collapsed=repo_key in collapsed_repos,
            prs=group_prs,
        )))

    result.sort(key=lambda t: (-t[0], t[1]))
    return [g for _, _, g in result]
