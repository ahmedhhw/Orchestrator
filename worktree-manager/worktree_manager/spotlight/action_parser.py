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

        N = len(spec.slots)
        rem = tokens[consumed:]
        rem_count = len(rem)

        if rem_count == 0 and not ends_with_space:
            active_idx, committed_count, needle = 0, 0, ""
        elif rem_count <= N - 1:
            if ends_with_space:
                active_idx, committed_count, needle = rem_count, rem_count, ""
            else:
                active_idx = rem_count - 1
                committed_count = active_idx
                needle = rem[active_idx]
        elif rem_count == N:
            if ends_with_space:
                active_idx, committed_count, needle = N - 1, N, ""
            else:
                active_idx, committed_count, needle = N - 1, N - 1, rem[N - 1]
        else:
            active_idx = N - 1
            committed_count = N - 1
            needle = " ".join(rem[N - 1:])

        committed_args: dict[str, str] = {
            spec.slots[i].name: rem[i]
            for i in range(min(committed_count, N))
        }

        if committed_count == N:
            return ParseResult(
                action=spec, suggestions=[], filter_text="",
                executable=True, completion_kind="slot",
                committed_args=committed_args, slot_index=N,
            )

        active_slot = spec.slots[active_idx]
        candidates = active_slot.candidates(committed_args)
        suggestions = _prefix_filter(candidates, needle)
        return ParseResult(
            action=spec, suggestions=suggestions, filter_text=needle,
            executable=(len(suggestions) == 1),
            completion_kind="slot",
            committed_args=committed_args, slot_index=active_idx,
            all_candidates=candidates,
        )
