from worktree_manager.spotlight.action_parser import ActionParser
from worktree_manager.spotlight.action_registry import (
    ActionRegistry, ActionSpec, ArgSlot,
)


def _registry_with_project_action(projects):
    r = ActionRegistry()
    r.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: list(projects))],
        runner=lambda args: None,
    ))
    return r


def test_empty_input_returns_root_keywords_as_suggestions():
    r = _registry_with_project_action(["foo"])
    p = ActionParser(r)
    result = p.parse("")
    assert result.action is None
    assert result.suggestions == ["project"]
    assert result.executable is False


def test_partial_keyword_filters_root_keywords_by_prefix_case_insensitive():
    r = ActionRegistry()
    r.register(ActionSpec(name="open_project", keywords=["project"], slots=[]))
    r.register(ActionSpec(name="run_command", keywords=["command"], slots=[]))
    p = ActionParser(r)
    assert p.parse("PRO").suggestions == ["project"]
    assert p.parse("c").suggestions == ["command"]
    assert p.parse("xyz").suggestions == []


def test_exact_keyword_with_trailing_space_returns_all_slot_candidates():
    r = _registry_with_project_action(["alpha", "beta", "gamma"])
    p = ActionParser(r)
    result = p.parse("project ")
    assert result.action is not None
    assert result.action.name == "open_project"
    assert result.suggestions == ["alpha", "beta", "gamma"]


def test_exact_keyword_without_space_still_treats_keyword_as_complete():
    r = _registry_with_project_action(["alpha", "beta"])
    p = ActionParser(r)
    result = p.parse("project")
    assert result.action is not None
    assert result.suggestions == ["alpha", "beta"]


def test_keyword_with_partial_arg_filters_candidates_by_prefix():
    r = _registry_with_project_action(["foo", "foo-bar", "baz"])
    p = ActionParser(r)
    result = p.parse("project fo")
    assert result.suggestions == ["foo", "foo-bar"]


def test_prefix_match_is_case_insensitive():
    r = _registry_with_project_action(["Foo", "BAR"])
    p = ActionParser(r)
    assert p.parse("project f").suggestions == ["Foo"]
    assert p.parse("project ba").suggestions == ["BAR"]


def test_filter_supports_multi_word_candidate_names():
    r = _registry_with_project_action(["My Cool Project", "Other"])
    p = ActionParser(r)
    assert p.parse("project My").suggestions == ["My Cool Project"]
    assert p.parse("project Ot").suggestions == ["Other"]


def test_executable_true_when_filter_matches_exactly_one_candidate():
    r = _registry_with_project_action(["foo", "bar"])
    p = ActionParser(r)
    assert p.parse("project foo").executable is True


def test_executable_false_when_filter_matches_multiple_candidates():
    r = _registry_with_project_action(["foo", "foo-bar"])
    p = ActionParser(r)
    assert p.parse("project foo").executable is False


def test_executable_false_when_filter_matches_no_candidates():
    r = _registry_with_project_action(["foo"])
    p = ActionParser(r)
    assert p.parse("project zzz").executable is False


# ── Phase 1.2 tests ──────────────────────────────────────────────────────────

def test_partial_first_keyword_filters_root_keywords_substring():
    r = ActionRegistry()
    r.register(ActionSpec(name="open_project", keywords=["project"], slots=[]))
    r.register(ActionSpec(name="edit_project", keywords=["edit", "project"], slots=[]))
    p = ActionParser(r)
    assert p.parse("ed").suggestions == ["edit"]
    assert p.parse("pro").suggestions == ["project"]


def test_first_keyword_complete_with_trailing_space_lists_continuations():
    r = ActionRegistry()
    r.register(ActionSpec(name="edit_project", keywords=["edit", "project"], slots=[]))
    r.register(ActionSpec(name="edit_command", keywords=["edit", "command"], slots=[]))
    p = ActionParser(r)
    result = p.parse("edit ")
    assert result.action is None
    assert result.suggestions == ["project", "command"]
    assert result.completion_kind == "keyword"


def test_partial_continuation_filters_continuations_by_substring():
    r = ActionRegistry()
    r.register(ActionSpec(name="edit_project", keywords=["edit", "project"], slots=[]))
    r.register(ActionSpec(name="edit_command", keywords=["edit", "command"], slots=[]))
    p = ActionParser(r)
    assert p.parse("edit pro").suggestions == ["project"]
    assert p.parse("edit com").suggestions == ["command"]


def test_full_chain_then_slot_filters_candidates():
    r = ActionRegistry()
    r.register(ActionSpec(
        name="edit_project",
        keywords=["edit", "project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["alpha", "beta"])],
    ))
    p = ActionParser(r)
    result = p.parse("edit project al")
    assert result.action.name == "edit_project"
    assert result.suggestions == ["alpha"]
    assert result.completion_kind == "slot"


def test_zero_arg_keyword_action_is_executable_immediately():
    r = ActionRegistry()
    r.register(ActionSpec(name="settings", keywords=["settings"], slots=[]))
    p = ActionParser(r)
    result = p.parse("settings")
    assert result.action.name == "settings"
    assert result.executable is True
    assert result.suggestions == []


# ── Phase 1.3 tests ──────────────────────────────────────────────────────────

def test_multi_slot_lists_first_slot_candidates_after_keyword_then_space():
    r = ActionRegistry()
    r.register(ActionSpec(
        name="run_command",
        keywords=["command"],
        slots=[
            ArgSlot(name="repo", candidates=lambda prev: ["repoA", "repoB"]),
            ArgSlot(name="worktree", candidates=lambda prev: ["wt1"]),
            ArgSlot(name="cmd", candidates=lambda prev: ["runserver"]),
        ],
    ))
    p = ActionParser(r)
    result = p.parse("command ")
    assert result.slot_index == 0
    assert result.suggestions == ["repoA", "repoB"]
    assert result.committed_args == {}


def test_multi_slot_advances_to_second_slot_after_first_token_and_space():
    r = ActionRegistry()
    r.register(ActionSpec(
        name="run_command",
        keywords=["command"],
        slots=[
            ArgSlot(name="repo", candidates=lambda prev: ["repoA", "repoB"]),
            ArgSlot(
                name="worktree",
                candidates=lambda prev: {
                    "repoA": ["wt1", "wt2"], "repoB": ["wt3"],
                }.get(prev.get("repo"), []),
            ),
            ArgSlot(name="cmd", candidates=lambda prev: ["x"]),
        ],
    ))
    p = ActionParser(r)
    result = p.parse("command repoA ")
    assert result.slot_index == 1
    assert result.suggestions == ["wt1", "wt2"]
    assert result.committed_args == {"repo": "repoA"}


def test_multi_slot_filters_active_slot_by_partial_needle():
    r = ActionRegistry()
    r.register(ActionSpec(
        name="run_command",
        keywords=["command"],
        slots=[
            ArgSlot(name="repo", candidates=lambda prev: ["repoA"]),
            ArgSlot(name="worktree", candidates=lambda prev: ["main", "feat-1"]),
            ArgSlot(name="cmd", candidates=lambda prev: ["runserver", "runtests"]),
        ],
    ))
    p = ActionParser(r)
    result = p.parse("command repoA main run")
    assert result.slot_index == 2
    assert result.suggestions == ["runserver", "runtests"]
    assert result.committed_args == {"repo": "repoA", "worktree": "main"}


def test_multi_slot_executable_when_all_slots_filled_with_trailing_space():
    r = ActionRegistry()
    r.register(ActionSpec(
        name="switch_branch",
        keywords=["switch"],
        slots=[
            ArgSlot(name="worktree", candidates=lambda prev: ["wt1"]),
            ArgSlot(name="branch", candidates=lambda prev: ["main", "dev"]),
        ],
    ))
    p = ActionParser(r)
    result = p.parse("switch wt1 main ")
    assert result.executable is True
    assert result.committed_args == {"worktree": "wt1", "branch": "main"}
    assert result.suggestions == []


def test_slot_candidates_receive_previous_committed_args():
    seen = []
    r = ActionRegistry()
    r.register(ActionSpec(
        name="x",
        keywords=["x"],
        slots=[
            ArgSlot(name="a", candidates=lambda prev: ["a1"]),
            ArgSlot(name="b", candidates=lambda prev: (seen.append(dict(prev)) or ["b1"])),
        ],
    ))
    p = ActionParser(r)
    p.parse("x a1 ")
    assert seen[-1] == {"a": "a1"}
