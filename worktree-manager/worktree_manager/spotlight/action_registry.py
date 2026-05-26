from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ArgSlot:
    name: str
    candidates: Callable[[dict], list[str]]


@dataclass
class ActionSpec:
    name: str
    keywords: list[str]
    slots: list[ArgSlot] = field(default_factory=list)
    runner: Callable[[dict], None] = field(default=lambda args: None)
    description: str = ""


class ActionRegistry:
    def __init__(self):
        self._specs: list[ActionSpec] = []

    def register(self, spec: ActionSpec) -> None:
        self._specs.append(spec)

    def all_specs(self) -> list[ActionSpec]:
        return list(self._specs)

    def root_keywords(self) -> list[str]:
        seen: list[str] = []
        for spec in self._specs:
            kw = spec.keywords[0]
            if kw not in seen:
                seen.append(kw)
        return seen

    def get_by_name(self, name: str) -> ActionSpec | None:
        for spec in self._specs:
            if spec.name == name:
                return spec
        return None

    def find_by_keywords(self, keywords: list[str]) -> ActionSpec | None:
        for spec in self._specs:
            if spec.keywords == list(keywords):
                return spec
        return None

    def next_keywords(self, prefix: list[str]) -> list[str]:
        seen: list[str] = []
        n = len(prefix)
        for spec in self._specs:
            if len(spec.keywords) <= n:
                continue
            if spec.keywords[:n] != list(prefix):
                continue
            kw = spec.keywords[n]
            if kw not in seen:
                seen.append(kw)
        return seen

    def find_longest_keyword_match(
        self, tokens: list[str]
    ) -> tuple[ActionSpec | None, int]:
        best: ActionSpec | None = None
        best_len = 0
        for spec in self._specs:
            k = len(spec.keywords)
            if k > len(tokens):
                continue
            if spec.keywords == tokens[:k] and k > best_len:
                best = spec
                best_len = k
        return best, best_len
