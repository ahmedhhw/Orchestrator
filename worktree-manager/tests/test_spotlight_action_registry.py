from worktree_manager.spotlight.action_registry import (
    ActionRegistry, ActionSpec, ArgSlot,
)


def _make_spec(keywords, name="dummy", slots=None, runner=None):
    return ActionSpec(
        name=name,
        keywords=list(keywords),
        slots=list(slots or []),
        runner=runner or (lambda args: None),
    )


def test_registry_starts_empty():
    r = ActionRegistry()
    assert r.all_specs() == []
    assert r.root_keywords() == []


def test_register_adds_spec_to_all_specs():
    r = ActionRegistry()
    spec = _make_spec(["project"])
    r.register(spec)
    assert r.all_specs() == [spec]


def test_root_keywords_returns_unique_first_keywords_in_registration_order():
    r = ActionRegistry()
    r.register(_make_spec(["project"], name="open_project"))
    r.register(_make_spec(["edit", "project"], name="edit_project"))
    r.register(_make_spec(["command"], name="run_command"))
    assert r.root_keywords() == ["project", "edit", "command"]


def test_find_by_keywords_returns_exact_match():
    r = ActionRegistry()
    s1 = _make_spec(["project"], name="open_project")
    s2 = _make_spec(["edit", "project"], name="edit_project")
    r.register(s1)
    r.register(s2)
    assert r.find_by_keywords(["project"]) is s1
    assert r.find_by_keywords(["edit", "project"]) is s2


def test_find_by_keywords_returns_none_when_no_match():
    r = ActionRegistry()
    r.register(_make_spec(["project"]))
    assert r.find_by_keywords(["repo"]) is None
    assert r.find_by_keywords([]) is None


def test_arg_slot_candidates_is_a_callable_returning_strings():
    slot = ArgSlot(name="name", candidates=lambda: ["a", "b"])
    assert slot.candidates() == ["a", "b"]
