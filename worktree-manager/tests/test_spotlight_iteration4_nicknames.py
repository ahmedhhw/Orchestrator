"""Tests for Iteration 4: Nicknames + MRU."""
import pytest
from unittest.mock import MagicMock

from worktree_manager.spotlight.nickname_store import NicknameEntry, NicknameStore
from worktree_manager.spotlight.action_parser import ActionParser
from worktree_manager.spotlight.action_registry import ActionRegistry, ActionSpec, ArgSlot
from worktree_manager.config_store import ConfigStore


# ---------------------------------------------------------------------------
# NicknameStore
# ---------------------------------------------------------------------------

class _FakeConfigStore:
    def __init__(self):
        self._prefs: dict = {}

    def get_ui_pref(self, key, default=None):
        return self._prefs.get(key, default)

    def set_ui_pref(self, key, value) -> None:
        self._prefs[key] = value


def test_nickname_store_save_and_get():
    cs = _FakeConfigStore()
    store = NicknameStore(cs)
    entry = NicknameEntry(nickname="myproj", action_name="project", args={"name": "alpha"})
    store.save(entry)
    got = store.get("myproj")
    assert got is not None
    assert got.action_name == "project"
    assert got.args == {"name": "alpha"}


def test_nickname_store_get_missing_returns_none():
    cs = _FakeConfigStore()
    store = NicknameStore(cs)
    assert store.get("nope") is None


def test_nickname_store_all_returns_all():
    cs = _FakeConfigStore()
    store = NicknameStore(cs)
    store.save(NicknameEntry("a", "project", {"name": "A"}))
    store.save(NicknameEntry("b", "command", {"repo": "r", "worktree": "w", "name": "n"}))
    all_entries = store.all()
    assert set(all_entries.keys()) == {"a", "b"}


def test_nickname_store_delete():
    cs = _FakeConfigStore()
    store = NicknameStore(cs)
    store.save(NicknameEntry("a", "project", {"name": "A"}))
    store.delete("a")
    assert store.get("a") is None


def test_nickname_store_save_overwrites():
    cs = _FakeConfigStore()
    store = NicknameStore(cs)
    store.save(NicknameEntry("n", "project", {"name": "old"}))
    store.save(NicknameEntry("n", "project", {"name": "new"}))
    assert store.get("n").args == {"name": "new"}


# ---------------------------------------------------------------------------
# ConfigStore MRU
# ---------------------------------------------------------------------------

def test_config_store_push_mru_prepends(tmp_path):
    cs = ConfigStore(tmp_path / "cfg.json")
    cs.push_mru("project", {"name": "alpha"})
    cs.push_mru("command", {"repo": "r", "worktree": "w", "name": "n"})
    mru = cs.get_mru()
    assert mru[0]["action"] == "command"
    assert mru[1]["action"] == "project"


def test_config_store_push_mru_deduplicates(tmp_path):
    cs = ConfigStore(tmp_path / "cfg.json")
    cs.push_mru("project", {"name": "alpha"})
    cs.push_mru("command", {"repo": "r", "worktree": "w", "name": "n"})
    cs.push_mru("project", {"name": "alpha"})
    mru = cs.get_mru()
    assert len(mru) == 2
    assert mru[0]["action"] == "project"


def test_config_store_push_mru_cap(tmp_path):
    cs = ConfigStore(tmp_path / "cfg.json")
    for i in range(15):
        cs.push_mru("project", {"name": str(i)})
    mru = cs.get_mru()
    assert len(mru) == 10


# ---------------------------------------------------------------------------
# ActionParser — nickname + MRU
# ---------------------------------------------------------------------------

def _make_registry() -> ActionRegistry:
    reg = ActionRegistry()
    reg.register(ActionSpec(
        name="project",
        keywords=["project"],
        slots=[ArgSlot("name", lambda _: ["alpha", "beta"])],
        runner=lambda args: None,
    ))
    reg.register(ActionSpec(
        name="command",
        keywords=["command"],
        slots=[
            ArgSlot("repo", lambda _: ["repo1"]),
            ArgSlot("worktree", lambda _: ["wt1"]),
            ArgSlot("name", lambda _: ["runserver"]),
        ],
        runner=lambda args: None,
    ))
    return reg


def test_parser_empty_input_shows_mru_first():
    reg = _make_registry()
    cs = _FakeConfigStore()
    cs.set_ui_pref("mru", [
        {"action": "project", "args": {"name": "alpha"}},
    ])
    mru_labels = ["project alpha"]
    parser = ActionParser(reg, mru_labels=mru_labels)
    result = parser.parse("")
    assert result.suggestions[0] == "project alpha"
    assert "project" in result.suggestions


def test_parser_mru_deduped_from_keywords():
    reg = _make_registry()
    parser = ActionParser(reg, mru_labels=["project", "command"])
    result = parser.parse("")
    # "project" appears once even though it's both MRU and a root keyword.
    assert result.suggestions.count("project") == 1


def test_parser_nickname_exact_match():
    reg = _make_registry()
    cs = _FakeConfigStore()
    from worktree_manager.spotlight.nickname_store import NicknameStore
    ns = NicknameStore(cs)
    ns.save(NicknameEntry("myproj", "project", {"name": "alpha"}))
    parser = ActionParser(reg, nickname_store=ns)
    result = parser.parse("myproj")
    assert result.completion_kind == "nickname"
    assert result.executable is True
    assert result.nickname_action_name == "project"
    assert result.nickname_args == {"name": "alpha"}


def test_parser_nickname_not_triggered_with_space():
    reg = _make_registry()
    cs = _FakeConfigStore()
    from worktree_manager.spotlight.nickname_store import NicknameStore
    ns = NicknameStore(cs)
    ns.save(NicknameEntry("myproj", "project", {"name": "alpha"}))
    parser = ActionParser(reg, nickname_store=ns)
    # With trailing space, should not be a nickname match
    result = parser.parse("myproj ")
    assert result.completion_kind != "nickname"


def test_parser_nickname_shown_as_suggestion_at_root():
    reg = _make_registry()
    cs = _FakeConfigStore()
    from worktree_manager.spotlight.nickname_store import NicknameStore
    ns = NicknameStore(cs)
    ns.save(NicknameEntry("myproj", "project", {"name": "alpha"}))
    parser = ActionParser(reg, nickname_store=ns)
    result = parser.parse("my")
    assert "myproj" in result.suggestions


def test_parser_nickname_prefix_does_not_match_as_nickname():
    reg = _make_registry()
    cs = _FakeConfigStore()
    from worktree_manager.spotlight.nickname_store import NicknameStore
    ns = NicknameStore(cs)
    ns.save(NicknameEntry("myproj", "project", {"name": "alpha"}))
    parser = ActionParser(reg, nickname_store=ns)
    result = parser.parse("my")
    assert result.completion_kind != "nickname"


# ---------------------------------------------------------------------------
# ActionRegistry.get_by_name
# ---------------------------------------------------------------------------

def test_registry_get_by_name():
    reg = _make_registry()
    spec = reg.get_by_name("project")
    assert spec is not None
    assert spec.name == "project"


def test_registry_get_by_name_missing():
    reg = _make_registry()
    assert reg.get_by_name("nonexistent") is None


# ---------------------------------------------------------------------------
# SpotlightOverlay — nickname execution + on_action_executed callback
# ---------------------------------------------------------------------------

def _make_registry_with_callable():
    executed: list = []
    reg = ActionRegistry()
    reg.register(ActionSpec(
        name="project",
        keywords=["project"],
        slots=[ArgSlot("name", lambda _: ["alpha", "beta"])],
        runner=lambda args: executed.append(("project", args)),
    ))
    return reg, executed


def test_overlay_nickname_execution(qtbot):
    from worktree_manager.ui.spotlight_overlay import SpotlightOverlay
    from worktree_manager.spotlight.action_parser import ActionParser
    from worktree_manager.spotlight.nickname_store import NicknameStore

    reg, executed = _make_registry_with_callable()
    cs = _FakeConfigStore()
    ns = NicknameStore(cs)
    ns.save(NicknameEntry("myproj", "project", {"name": "alpha"}))
    parser = ActionParser(reg, nickname_store=ns)

    callbacks: list = []
    overlay = SpotlightOverlay(parser, on_action_executed=lambda name, args: callbacks.append((name, args)))
    qtbot.addWidget(overlay)
    overlay.show()

    from PySide6.QtCore import Qt
    overlay._edit.setText("myproj")
    qtbot.keyClick(overlay._edit, Qt.Key_Return)

    assert executed == [("project", {"name": "alpha"})]
    assert callbacks == [("project", {"name": "alpha"})]
    assert not overlay.isVisible()


def test_overlay_normal_execution_calls_on_action_executed(qtbot):
    from worktree_manager.ui.spotlight_overlay import SpotlightOverlay
    from worktree_manager.spotlight.action_parser import ActionParser

    reg, executed = _make_registry_with_callable()
    parser = ActionParser(reg)

    callbacks: list = []
    overlay = SpotlightOverlay(parser, on_action_executed=lambda name, args: callbacks.append((name, args)))
    qtbot.addWidget(overlay)
    overlay.show()

    from PySide6.QtCore import Qt
    overlay._edit.setText("project alpha")
    qtbot.keyClick(overlay._edit, Qt.Key_Return)

    assert len(executed) == 1
    assert executed[0][0] == "project"
    assert callbacks == [("project", {"name": "alpha"})]


def test_overlay_no_callback_when_none(qtbot):
    from worktree_manager.ui.spotlight_overlay import SpotlightOverlay
    from worktree_manager.spotlight.action_parser import ActionParser

    reg, executed = _make_registry_with_callable()
    parser = ActionParser(reg)
    # No callback — should not crash
    overlay = SpotlightOverlay(parser)
    qtbot.addWidget(overlay)
    overlay.show()

    from PySide6.QtCore import Qt
    overlay._edit.setText("project alpha")
    qtbot.keyClick(overlay._edit, Qt.Key_Return)
    assert len(executed) == 1


# ---------------------------------------------------------------------------
# App wiring: 'nicknames' action
# ---------------------------------------------------------------------------

def _seed_cfg(tmp_path):
    from worktree_manager.config_store import ConfigStore
    cfg = tmp_path / "config.json"
    ConfigStore(path=cfg)  # create empty
    return cfg


def _patch_app(monkeypatch, cfg):
    from worktree_manager.config_store import ConfigStore
    monkeypatch.setattr(
        "worktree_manager.cli.ConfigStore",
        lambda: ConfigStore(path=cfg),
    )


def test_nicknames_action_is_registered(qtbot, tmp_path, monkeypatch):
    from worktree_manager.cli import App
    _patch_app(monkeypatch, _seed_cfg(tmp_path))
    app = App()
    qtbot.addWidget(app)
    names = [s.name for s in app.spotlight_registry().all_specs()]
    assert "manage_nicknames" in names


def test_nicknames_action_opens_dialog(qtbot, tmp_path, monkeypatch):
    from worktree_manager.cli import App
    from worktree_manager.ui.manage_nicknames_dialog import ManageNicknamesDialog
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit

    _patch_app(monkeypatch, _seed_cfg(tmp_path))

    opened = []
    monkeypatch.setattr(
        ManageNicknamesDialog, "exec",
        lambda self: opened.append(self) or 0,
    )

    app = App()
    qtbot.addWidget(app)
    overlay = app.open_spotlight_for_test()
    edit = overlay.findChild(QLineEdit)
    edit.setText("nicknames")
    qtbot.keyClick(edit, Qt.Key_Return)

    assert len(opened) == 1
    assert isinstance(opened[0], ManageNicknamesDialog)
