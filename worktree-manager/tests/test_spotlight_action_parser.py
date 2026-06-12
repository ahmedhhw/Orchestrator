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


def _registry_with_command_action(repos, worktrees_by_repo=None, cmds=None):
    """Multi-slot action: command [repo] [worktree] [cmd]."""
    if worktrees_by_repo is None:
        worktrees_by_repo = {}
    if cmds is None:
        cmds = []
    r = ActionRegistry()
    r.register(ActionSpec(
        name="run_command",
        keywords=["command"],
        slots=[
            ArgSlot(name="repo", candidates=lambda prev, rs=repos: list(rs)),
            ArgSlot(
                name="worktree",
                candidates=lambda prev, wbr=worktrees_by_repo: wbr.get(prev.get("repo"), []),
            ),
            ArgSlot(name="cmd", candidates=lambda prev, cs=cmds: list(cs)),
        ],
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


def test_executable_true_when_filter_is_exact_match_even_if_another_candidate_shares_prefix():
    # "foo" is an exact candidate — typing it and pressing Enter should execute,
    # regardless of "foo-bar" also existing.
    r = _registry_with_project_action(["foo", "foo-bar"])
    p = ActionParser(r)
    result = p.parse("project foo")
    assert result.executable is True
    assert result.committed_args == {"name": "foo"}


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


# ── Spaced-slot-values tests ──────────────────────────────────────────────────

def test_spaced_project_name_with_trailing_space_is_committed_and_executable():
    r = _registry_with_project_action(["My App", "Other"])
    p = ActionParser(r)
    result = p.parse("project My App ")
    assert result.committed_args == {"name": "My App"}
    assert result.slot_index == 1
    assert result.executable is True
    assert result.suggestions == []


def test_spaced_project_name_without_trailing_space_is_committed_and_executable():
    # Typing the full spaced name without a trailing space should be recognised as
    # committed (exact match) and executable — Enter should run it immediately.
    r = _registry_with_project_action(["My App", "Other"])
    p = ActionParser(r)
    result = p.parse("project My App")
    assert result.slot_index == 1  # fully committed
    assert result.committed_args == {"name": "My App"}
    assert result.executable is True


def test_typing_first_word_of_spaced_name_keeps_full_name_suggested():
    r = _registry_with_project_action(["My App", "Other"])
    p = ActionParser(r)
    result = p.parse("project My")
    assert result.suggestions == ["My App"]
    assert result.slot_index == 0
    assert result.filter_text == "My"


def test_typing_across_internal_space_filters_by_whole_needle():
    r = _registry_with_project_action(["My App", "My Other"])
    p = ActionParser(r)
    result = p.parse("project My A")
    assert result.suggestions == ["My App"]
    assert result.filter_text == "My A"


def test_single_word_project_name_commits_with_trailing_space():
    r = _registry_with_project_action(["solo", "other"])
    p = ActionParser(r)
    result = p.parse("project solo ")
    assert result.committed_args == {"name": "solo"}
    assert result.executable is True
    assert result.suggestions == []


def test_spaced_value_in_non_final_slot_commits_when_followed_by_space():
    r = _registry_with_command_action(
        repos=["My Repo", "Other Repo"],
        worktrees_by_repo={"My Repo": ["main"], "Other Repo": ["dev"]},
        cmds=["run"],
    )
    p = ActionParser(r)
    result = p.parse("command My Repo ")
    assert result.committed_args == {"repo": "My Repo"}
    assert result.slot_index == 1


def test_spaced_values_in_every_slot_all_commit():
    r = _registry_with_command_action(
        repos=["My Repo"],
        worktrees_by_repo={"My Repo": ["main"]},
        cmds=["Run Tests"],
    )
    p = ActionParser(r)
    result = p.parse("command My Repo main Run Tests ")
    assert result.committed_args == {"repo": "My Repo", "worktree": "main", "cmd": "Run Tests"}
    assert result.executable is True
    assert result.slot_index == 3


def test_longest_matching_candidate_wins_for_prefix_nested_names():
    r = _registry_with_project_action(["Two Word", "Two Word Thing"])
    p = ActionParser(r)
    result_long = p.parse("project Two Word Thing ")
    assert result_long.committed_args == {"name": "Two Word Thing"}
    assert result_long.executable is True

    result_short = p.parse("project Two Word ")
    assert result_short.committed_args == {"name": "Two Word"}
    assert result_short.executable is True


def test_typed_value_not_a_candidate_keeps_slot_active_no_suggestions():
    r = _registry_with_project_action(["My App"])
    p = ActionParser(r)
    result = p.parse("project Zzz ")
    assert result.suggestions == []
    assert result.executable is False
    assert result.slot_index == 0
