from dataclasses import dataclass


@dataclass
class NicknameEntry:
    nickname: str
    action_name: str
    args: dict


class NicknameStore:
    """Persists nickname→action mappings via ConfigStore's ui prefs."""

    _KEY = "nicknames"

    def __init__(self, config_store):
        self._store = config_store

    def all(self) -> dict[str, NicknameEntry]:
        raw: dict = self._store.get_ui_pref(self._KEY, {})
        return {
            nick: NicknameEntry(
                nickname=nick,
                action_name=v["action"],
                args=v.get("args", {}),
            )
            for nick, v in raw.items()
        }

    def get(self, nickname: str) -> NicknameEntry | None:
        return self.all().get(nickname)

    def save(self, entry: NicknameEntry) -> None:
        raw = self._store.get_ui_pref(self._KEY, {})
        raw[entry.nickname] = {"action": entry.action_name, "args": dict(entry.args)}
        self._store.set_ui_pref(self._KEY, raw)

    def delete(self, nickname: str) -> None:
        raw = self._store.get_ui_pref(self._KEY, {})
        raw.pop(nickname, None)
        self._store.set_ui_pref(self._KEY, raw)
