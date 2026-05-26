from dataclasses import dataclass, field

from worktree_manager.spotlight.action_registry import ActionRegistry, ActionSpec


@dataclass
class ParseResult:
    action: ActionSpec | None
    suggestions: list[str]
    filter_text: str = ""
    executable: bool = False


def _substring_filter(items: list[str], needle: str) -> list[str]:
    if not needle:
        return list(items)
    needle = needle.lower()
    return [item for item in items if needle in item.lower()]


class ActionParser:
    def __init__(self, registry: ActionRegistry):
        self._registry = registry

    def parse(self, text: str) -> ParseResult:
        roots = self._registry.root_keywords()

        stripped = text.lstrip()
        if not stripped:
            return ParseResult(action=None, suggestions=list(roots))

        if " " in stripped:
            first, _, remainder = stripped.partition(" ")
        else:
            first, remainder = stripped, ""

        spec = self._registry.find_by_keywords([first])
        if spec is not None and spec.slots:
            slot = spec.slots[0]
            filter_text = remainder
            candidates = slot.candidates()
            suggestions = _substring_filter(candidates, filter_text)
            executable = len(suggestions) == 1
            return ParseResult(
                action=spec,
                suggestions=suggestions,
                filter_text=filter_text,
                executable=executable,
            )

        return ParseResult(
            action=None,
            suggestions=_substring_filter(roots, stripped),
            filter_text=stripped,
        )
