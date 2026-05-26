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


def test_arg_slot_candidates_is_a_callable_receiving_prev_args():
    slot = ArgSlot(name="name", candidates=lambda prev: ["a", "b"])
    assert slot.candidates({}) == ["a", "b"]


# ── Phase 1.1 tests ──────────────────────────────────────────────────────────

def test_next_keywords_lists_first_level_after_empty_prefix():
    r = ActionRegistry()
    r.register(_make_spec(["project"], name="p"))
    r.register(_make_spec(["edit", "project"], name="ep"))
    r.register(_make_spec(["edit", "command"], name="ec"))
    assert r.next_keywords([]) == ["project", "edit"]


def test_next_keywords_lists_continuations_after_partial_prefix():
    r = ActionRegistry()
    r.register(_make_spec(["edit", "project"], name="ep"))
    r.register(_make_spec(["edit", "command"], name="ec"))
    r.register(_make_spec(["project"], name="p"))
    assert r.next_keywords(["edit"]) == ["project", "command"]


def test_next_keywords_returns_empty_when_no_chain_extends_prefix():
    r = ActionRegistry()
    r.register(_make_spec(["project"], name="p"))
    assert r.next_keywords(["edit"]) == []


def test_find_longest_keyword_match_picks_longest_prefix():
    r = ActionRegistry()
    r.register(_make_spec(["edit", "project"], name="ep"))
    r.register(_make_spec(["project"], name="p"))
    spec, n = r.find_longest_keyword_match(["edit", "project", "foo"])
    assert spec.name == "ep"
    assert n == 2


def test_find_longest_keyword_match_returns_none_when_no_prefix_matches():
    r = ActionRegistry()
    r.register(_make_spec(["project"], name="p"))
    spec, n = r.find_longest_keyword_match(["xyz"])
    assert spec is None and n == 0


def test_arg_slot_candidates_receives_prev_args():
    seen = []
    slot = ArgSlot(name="cmd", candidates=lambda prev: seen.append(dict(prev)) or ["x"])
    assert slot.candidates({"repo": "r1"}) == ["x"]
    assert seen == [{"repo": "r1"}]
