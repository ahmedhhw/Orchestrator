from worktree_manager.spotlight.action_parser import ActionParser
from worktree_manager.spotlight.action_registry import (
    ActionRegistry, ActionSpec, ArgSlot,
)


def _registry_with_project_action(projects):
    r = ActionRegistry()
    r.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda: list(projects))],
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


def test_partial_keyword_filters_root_keywords_by_substring_case_insensitive():
    r = ActionRegistry()
    r.register(ActionSpec(name="open_project", keywords=["project"], slots=[]))
    r.register(ActionSpec(name="run_command", keywords=["command"], slots=[]))
    p = ActionParser(r)
    assert p.parse("PRO").suggestions == ["project"]
    assert p.parse("o").suggestions == ["project", "command"]
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


def test_keyword_with_partial_arg_filters_candidates_by_substring():
    r = _registry_with_project_action(["foo", "foo-bar", "baz"])
    p = ActionParser(r)
    result = p.parse("project fo")
    assert result.suggestions == ["foo", "foo-bar"]


def test_substring_match_is_case_insensitive():
    r = _registry_with_project_action(["Foo", "BAR"])
    p = ActionParser(r)
    assert p.parse("project f").suggestions == ["Foo"]
    assert p.parse("project ar").suggestions == ["BAR"]


def test_filter_supports_multi_word_candidate_names():
    r = _registry_with_project_action(["My Cool Project", "Other"])
    p = ActionParser(r)
    assert p.parse("project my co").suggestions == ["My Cool Project"]
    assert p.parse("project Cool").suggestions == ["My Cool Project"]


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
