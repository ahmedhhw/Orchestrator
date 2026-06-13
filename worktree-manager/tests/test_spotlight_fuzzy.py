from worktree_manager.spotlight.fuzzy import fuzzy_score, fuzzy_filter


def test_subsequence_matches_with_gaps():
    assert fuzzy_score("wsch", "worktree switch") is not None
    assert fuzzy_score("zx", "worktree switch") is None


def test_empty_needle_scores_neutral_and_keeps_all():
    assert fuzzy_score("", "anything") == 0
    items = ["beta", "alpha", "gamma"]
    assert fuzzy_filter(items, "") == items


def test_contiguous_run_outranks_scattered():
    # "sw" in "switch" is contiguous at position 0 — high score
    # "sw" in "s_worktree" — s at 0, w at 2 — scattered
    contiguous = fuzzy_score("sw", "switch")
    scattered = fuzzy_score("sw", "s-worktree")
    assert contiguous is not None
    assert scattered is not None
    assert contiguous > scattered


def test_start_of_string_outranks_late_start():
    # needle "ma" starts at index 0 in "main" vs index 2 in "xymain"
    early = fuzzy_score("ma", "main")
    late = fuzzy_score("ma", "xymain")
    assert early is not None
    assert late is not None
    assert early > late


def test_word_start_match_is_boosted():
    # "ws" matching at word boundaries: "w" starts "worktree", "s" starts "switch"
    # vs "ws" matching mid-word: "w" at 2, "s" at 4 in "xxwxsx"
    word_boundary = fuzzy_score("ws", "worktree switch")
    mid_word = fuzzy_score("ws", "xxwxsx")
    assert word_boundary is not None
    assert mid_word is not None
    assert word_boundary > mid_word


def test_filter_sorts_best_first_with_stable_tiebreak():
    # "mn" matches "main" (word start, early) better than "xmxnx" (scattered, late)
    items = ["xmxnx", "main"]
    result = fuzzy_filter(items, "mn")
    assert result[0] == "main"
    assert result[1] == "xmxnx"

    # Tiebreak: original input order preserved for equal scores
    result2 = fuzzy_filter(["alpha_beta", "alpha_beta_extra"], "ab")
    assert result2[0] == "alpha_beta"  # shorter span wins or same — original order stable


def test_filter_drops_non_matches():
    items = ["main", "zzqq", "master", "notmatch"]
    result = fuzzy_filter(items, "zzqq")
    assert result == ["zzqq"]

    # needle that is a non-subsequence of all
    result2 = fuzzy_filter(["alpha", "beta"], "zz")
    assert result2 == []
