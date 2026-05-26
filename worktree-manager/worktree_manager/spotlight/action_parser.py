from dataclasses import dataclass, field

from worktree_manager.spotlight.action_registry import ActionRegistry, ActionSpec


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


def _substring_filter(items: list[str], needle: str) -> list[str]:
    if not needle:
        return list(items)
    needle = needle.lower()
    return [item for item in items if item.lower().startswith(needle)]


class ActionParser:
    def __init__(self, registry: ActionRegistry):
        self._registry = registry

    def parse(self, text: str) -> ParseResult:
        roots = list(self._registry.root_keywords())
        if not text.strip():
            return ParseResult(
                action=None,
                suggestions=roots,
                completion_kind="keyword",
                all_candidates=roots,
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
            return ParseResult(
                action=None,
                suggestions=_substring_filter(candidates, partial),
                filter_text=partial,
                completion_kind="keyword",
                all_candidates=candidates,
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
        suggestions = _substring_filter(candidates, needle)
        return ParseResult(
            action=spec, suggestions=suggestions, filter_text=needle,
            executable=(len(suggestions) == 1),
            completion_kind="slot",
            committed_args=committed_args, slot_index=active_idx,
            all_candidates=candidates,
        )
