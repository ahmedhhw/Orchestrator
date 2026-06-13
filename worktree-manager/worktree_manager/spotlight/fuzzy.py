"""Fuzzy (subsequence) scorer and filter for the spotlight parser."""
from __future__ import annotations

BONUS_CONTIGUOUS = 10
BONUS_START = 15
BONUS_WORD_START = 8
PENALTY_GAP = 1
PENALTY_LEADIN = 1
PENALTY_CANDIDATE_LENGTH = 1  # small per-char cost so shorter candidates rank higher on tie


def fuzzy_score(needle: str, candidate: str) -> int | None:
    """Return a score >= 0 if needle is a subsequence of candidate, else None.

    Higher score = better match.
    """
    if needle == "":
        return 0

    nl = needle.lower()
    cl = candidate.lower()

    # Walk candidate left-to-right, consuming needle chars in order.
    matched: list[int] = []
    ni = 0
    for ci, ch in enumerate(cl):
        if ch == nl[ni]:
            matched.append(ci)
            ni += 1
            if ni == len(nl):
                break

    if ni < len(nl):
        return None  # not all needle chars found

    score = 0

    # Bonus for contiguous pairs of matched indices.
    for a, b in zip(matched, matched[1:]):
        if b == a + 1:
            score += BONUS_CONTIGUOUS

    # Bonus if match starts at index 0.
    if matched[0] == 0:
        score += BONUS_START

    # Bonus for each match at a word boundary (start of string or after space/-/_).
    for i in matched:
        if i == 0 or cl[i - 1] in " -_":
            score += BONUS_WORD_START

    # Penalty for total span gap (spread-out matches).
    gap = matched[-1] - matched[0] - (len(nl) - 1)
    score -= PENALTY_GAP * gap

    # Penalty for late start.
    score -= PENALTY_LEADIN * matched[0]

    # Small penalty for longer candidates — shorter is more specific.
    score -= PENALTY_CANDIDATE_LENGTH * len(cl)

    return score


def fuzzy_filter(items: list[str], needle: str) -> list[str]:
    """Return items that are fuzzy-subsequence matches, sorted best-first.

    Empty needle returns items in original order (all kept).
    """
    if needle == "":
        return list(items)

    scored: list[tuple[int, int, str]] = []
    for idx, item in enumerate(items):
        s = fuzzy_score(needle, item)
        if s is not None:
            scored.append((s, idx, item))

    scored.sort(key=lambda t: (-t[0], t[1]))
    return [item for _, _, item in scored]
