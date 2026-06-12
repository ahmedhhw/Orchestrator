from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from worktree_manager.spotlight.action_registry import ActionRegistry, ActionSpec

if TYPE_CHECKING:
    from worktree_manager.spotlight.nickname_store import NicknameStore


@dataclass
class ParseResult:
    action: ActionSpec | None
    suggestions: list[str]
    filter_text: str = ""
    executable: bool = False
    completion_kind: str = "keyword"
    committed_args: dict[str, str] = field(default_factory=dict)
    slot_index: int = 0
    all_candidates: list[str] = field(default_factory=list)
    # Set when input exactly matches a nickname — the runner is called directly.
    nickname_action_name: str | None = None
    nickname_args: dict | None = None


def _prefix_filter(items: list[str], needle: str) -> list[str]:
    if not needle:
        return list(items)
    needle = needle.lower()
    return [item for item in items if item.lower().startswith(needle)]


def _arg_string_after_keywords(text: str, keywords: list[str]) -> str:
    """Return the substring of text after the matched keyword tokens (and their trailing space).

    Keywords are matched as leading whitespace-delimited tokens; the remainder
    (including internal spaces) is returned verbatim.
    """
    rest = text.lstrip()
    for kw in keywords:
        if rest.lower().startswith(kw.lower()):
            rest = rest[len(kw):]
        # Strip at most one separating space between keyword tokens.
        if rest.startswith(" "):
            rest = rest[1:]
    return rest


def _longest_committed_candidate(rest: str, cands: list[str]) -> str | None:
    """Return the longest candidate c such that rest starts with c + ' ' or rest == c.

    An exact match with no trailing space (rest == c) counts as committed when
    it is the final token — nothing follows it.
    """
    best: str | None = None
    for c in cands:
        if (rest == c or rest.startswith(c + " ")) and (best is None or len(c) > len(best)):
            best = c
    return best


class ActionParser:
    def __init__(
        self,
        registry: ActionRegistry,
        nickname_store: NicknameStore | None = None,
        mru_labels: list[str] | None = None,
    ):
        self._registry = registry
        self._nickname_store = nickname_store
        self._mru_labels = mru_labels or []

    def parse(self, text: str) -> ParseResult:
        roots = list(self._registry.root_keywords())

        if not text.strip():
            # Prepend MRU labels ahead of root keywords (deduped).
            seen: set[str] = set()
            suggestions: list[str] = []
            for label in self._mru_labels:
                if label not in seen:
                    suggestions.append(label)
                    seen.add(label)
            for kw in roots:
                if kw not in seen:
                    suggestions.append(kw)
                    seen.add(kw)
            return ParseResult(
                action=None,
                suggestions=suggestions,
                completion_kind="keyword",
                all_candidates=suggestions,
            )

        # Exact nickname match on the whole input (single token, no trailing space).
        stripped = text.strip()
        ends_with_space_early = text != text.rstrip()
        if self._nickname_store is not None and " " not in stripped and not ends_with_space_early:
            entry = self._nickname_store.get(stripped)
            if entry is not None:
                return ParseResult(
                    action=None,
                    suggestions=[stripped],
                    filter_text="",
                    executable=True,
                    completion_kind="nickname",
                    nickname_action_name=entry.action_name,
                    nickname_args=dict(entry.args),
                )

        ends_with_space = text != text.rstrip()
        tokens = text.split()
        spec, consumed = self._registry.find_longest_keyword_match(tokens)

        if spec is None:
            if ends_with_space:
                prefix, partial = tokens, ""
            else:
                prefix, partial = tokens[:-1], tokens[-1]
            candidates = self._registry.next_keywords(prefix)
            # Also include nickname names that start with the partial token.
            if self._nickname_store is not None and not prefix:
                nick_names = list(self._nickname_store.all().keys())
                for n in _prefix_filter(nick_names, partial):
                    if n not in candidates:
                        candidates = list(candidates) + [n]
            return ParseResult(
                action=None,
                suggestions=_prefix_filter(candidates, partial),
                filter_text=partial,
                completion_kind="keyword",
                all_candidates=list(candidates),
            )

        if not spec.slots:
            return ParseResult(
                action=spec, suggestions=[], filter_text="",
                executable=True, completion_kind="slot",
            )

        arg_str = _arg_string_after_keywords(text, spec.keywords)

        committed: dict[str, str] = {}
        rest = arg_str
        for i, slot in enumerate(spec.slots):
            cands = slot.candidates(committed)
            match = _longest_committed_candidate(rest, cands)
            if match is None:
                needle = rest
                suggestions = _prefix_filter(cands, needle)
                return ParseResult(
                    action=spec, suggestions=suggestions, filter_text=needle,
                    executable=(len(suggestions) == 1),
                    completion_kind="slot",
                    committed_args=committed, slot_index=i,
                    all_candidates=cands,
                )
            committed[slot.name] = match
            rest = rest[len(match) + 1:]  # +1 to strip the single space separator

        return ParseResult(
            action=spec, suggestions=[], filter_text="",
            executable=True, completion_kind="slot",
            committed_args=committed, slot_index=len(spec.slots),
        )
