from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ArgSlot:
    name: str
    candidates: Callable[[], list[str]]


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

    def find_by_keywords(self, keywords: list[str]) -> ActionSpec | None:
        for spec in self._specs:
            if spec.keywords == list(keywords):
                return spec
        return None
