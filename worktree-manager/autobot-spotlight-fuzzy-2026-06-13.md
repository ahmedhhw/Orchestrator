<!-- autobot-status
stage: 7
iteration: 1
gate: confirmed
updated: 2026-06-13
-->

# Autobot — Spotlight Fuzzy Search + Auto-Commit

Feature: add **fuzzy matching** to the spotlight overlay's suggestion filtering, and
**auto-replace** the user's typed fragment with the matched token + a trailing space the
moment the fragment unambiguously identifies a single token.

Affected code:
- [spotlight_overlay.py](worktree_manager/ui/spotlight_overlay.py) — UI / input handling
- [action_parser.py](worktree_manager/spotlight/action_parser.py) — filtering + parse pipeline

## Frontend Design

The only "screen" is the spotlight overlay: a text field, a caption, and a suggestion list.
Visuals don't change — what changes is **which rows appear**, **their order**, and **when the
text field auto-rewrites itself**. The mocks below show the behavioural states.

Legend: `│cursor│` marks the text-field caret. `▸` marks the highlighted (row 0) suggestion.

### State A — Fuzzy match surfaces non-prefix results
Today `switch` would NOT match `wsch` (not a prefix). With fuzzy matching, a subsequence hit ranks and shows it.

```
┌────────────────────────────────────────────┐
│ > wsch│                                     │
├────────────────────────────────────────────┤
│ COMMANDS                                     │
│ ▸ worktree switch                            │   ← "w·sch" subsequence of "worktree switch"
│   worktree show                              │
└────────────────────────────────────────────┘
```

### State B — Ranked order (best match first, auto-selected at row 0)
Closer / earlier / more-contiguous matches sort above looser ones.

```
┌────────────────────────────────────────────┐
│ > mn│                                        │
├────────────────────────────────────────────┤
│ BRANCHES                                     │
│ ▸ main                                       │   ← contiguous-ish, short → top
│   maint-notes                                │
│   moonbeam-nine                              │
└────────────────────────────────────────────┘
```

### State C — Auto-commit on a UNIQUE match (the key new behaviour)
The instant the typed fragment matches exactly one candidate, the field rewrites the
fragment to the full token + a space, and the parser advances to the next slot.

```
Before (user has typed "switch ma", only one branch matches "ma"):
┌────────────────────────────────────────────┐
│ > worktree switch ma│                        │
├────────────────────────────────────────────┤
│ BRANCHES                                     │
│ ▸ main                                       │   ← the ONLY remaining candidate
└────────────────────────────────────────────┘

After (auto-rewrite fires — no Enter pressed):
┌────────────────────────────────────────────┐
│ > worktree switch main │                     │   ← fragment "ma" → "main ", caret after space
├────────────────────────────────────────────┤
│ (next slot's candidates, or executable)      │
└────────────────────────────────────────────┘
```

### State D — Ambiguous prefix does NOT auto-commit (guard)
While multiple candidates remain, OR the fragment is a prefix of a longer candidate,
nothing is rewritten — the user keeps typing freely.

```
┌────────────────────────────────────────────┐
│ > worktree switch ma│                        │   ← "main" AND "master" both match
├────────────────────────────────────────────┤
│ BRANCHES                                     │
│ ▸ main                                       │
│   master                                     │   ← >1 candidate → NO auto-commit
└────────────────────────────────────────────┘
```

### State E — No match (unchanged from today)
Fuzzy finds nothing → empty list, field stays as typed, invalid flag on Enter as today.

```
┌────────────────────────────────────────────┐
│ > zzqq│                                      │
├────────────────────────────────────────────┤
│ (no suggestions; caption hidden)             │
└────────────────────────────────────────────┘
```

### Clarifying questions
1. **Fuzzy algorithm:** subsequence match with a relevance rank (fzf-lite: contiguous runs,
   start-of-word, and earliness boost ordering)? Or plain unranked subsequence? I'm proposing
   **ranked subsequence, no external dependency**.
2. **Auto-commit trigger:** fire only when the fuzzy result is **exactly one candidate** AND the
   fragment is not itself a strict prefix of a still-longer candidate. Is "exactly one candidate"
   the rule you want, or should an **exact full-token type-through** (e.g. typing `main` fully even
   while `master` exists) also auto-commit? I'm proposing **auto-commit when (a) exactly one
   candidate remains, or (b) the fragment exactly equals a candidate that no longer candidate
   extends**.
3. **Scope of auto-commit:** apply to **all slots** (repos, branches, commands, …) and to **root
   keywords** (e.g. `wor` → `worktree `)? I'm proposing **yes, everywhere the suggestion list
   resolves to one**.
4. **Backspace after an auto-commit:** if `ma`→`main ` auto-fires, then the user hits backspace,
   they'd delete the trailing space and land on `main` — acceptable? (Standard behaviour; no
   special undo. I'm proposing **no special handling**.)

### Resolved decisions
- **Fuzzy algorithm:** ranked subsequence (fzf-lite), no external dependency.
- **Auto-commit trigger:** only when the candidate set narrows to **exactly one**. An exact
  full-token type-through that still has a longer candidate (`main` while `master` exists) does
  **NOT** auto-commit.
- **Scope:** auto-commit applies everywhere the suggestion list resolves to one — root keywords
  and every slot.
- **Backspace:** no special handling.

## Backend Design

Two independent pieces of logic. (1) replaces the matching predicate inside the parser; (2) adds
an auto-commit decision the overlay consults on every keystroke. The parse pipeline, slot model,
nickname handling, and `_commit` rewrite are all **unchanged** — we only swap the filter and add
one trigger.

### Concept 1 — Fuzzy scorer (`fuzzy_score`)

A pure function: given a `needle` and a `candidate`, return either "no match" or a numeric score
(higher = better). Matching is **subsequence** — every char of `needle` appears in `candidate`
in order, case-insensitive, gaps allowed. Scoring rewards the qualities that make fzf feel right.

```
fuzzy_score(needle, candidate) -> int | None:
    if needle empty: return 0            # empty needle matches everything, neutral score
    walk candidate left→right matching needle chars in order (case-insensitive)
    if not all needle chars consumed: return None    # not a subsequence → no match
    score = 0
    score += BONUS_CONTIGUOUS  * (count of adjacent matched-char pairs)
    score += BONUS_START       if first match is at candidate index 0
    score += BONUS_WORD_START  * (matches landing right after a space/'-'/'_')
    score -= PENALTY_GAP       * (total skipped chars between first and last match)
    score -= PENALTY_LEADIN    * (index of first matched char)   # earlier start is better
    return score
```

```
fuzzy_filter(items, needle) -> list[str]:
    if needle empty: return list(items)          # preserve caller's original order (MRU etc.)
    scored = [(score, original_index, item) for item in items
              if (score := fuzzy_score(needle, item)) is not None]
    sort by (-score, original_index)             # best score first; stable tie-break on input order
    return [item for _, _, item in scored]
```

`_prefix_filter` in [action_parser.py](worktree_manager/spotlight/action_parser.py) is replaced
by `fuzzy_filter` at all three call sites (the partial-keyword branch, the nickname branch, and
the slot branch). `filter_text` semantics are unchanged — it's still the raw typed fragment; only
the *set and order* of suggestions change.

### Concept 2 — Auto-commit decision (`should_autocommit`)

The overlay already knows how to rewrite the field — `_commit(text, row_text)` in
[spotlight_overlay.py](worktree_manager/ui/spotlight_overlay.py#L126) strips `filter_text` and
appends `row_text + " "`. The new logic only decides **whether** to call it automatically.

Rule: auto-commit iff, for the current parse result, there is a **non-empty filter fragment** and
**exactly one** suggestion, and that single suggestion is **not** the fragment we already fully
committed (avoid re-firing on the trailing-space state).

```
should_autocommit(result) -> str | None:
    # returns the row_text to commit, or None
    if result.filter_text == "":      return None   # nothing typed in this slot → user just landed
    if len(result.suggestions) != 1:  return None   # 0 or >1 candidates → keep typing
    only = result.suggestions[0]
    if only == result.filter_text:    return None   # already exactly typed; commit happens on Enter
    return only
```

### Concept 3 — Wiring auto-commit into keystrokes (recursion guard)

`_on_text_changed` fires on every keystroke. Calling `_edit.setText(...)` inside it re-enters
`_on_text_changed`. A reentrancy guard prevents the loop; after the rewrite, a single re-parse
renders the next slot's suggestions.

```
_on_text_changed(text):
    if self._suppress_change: return        # guard: ignore programmatic edits
    clear error / invalid
    result = parser.parse(text)
    row = should_autocommit(result)
    if row is not None:
        new_text = self._commit(text, row)
        self._suppress_change = True
        self._edit.setText(new_text)        # caret goes to end automatically
        self._suppress_change = False
        self._refresh(new_text)             # render next slot from the committed text
        return
    self._refresh(text)
```

## Iteration Plan

- Iteration 0 — Fuzzy filtering in the parser
- Iteration 1 — Auto-commit on a unique match

### Iteration 0 — Fuzzy filtering in the parser
**Context file:** [Iteration 0 context](autobot-spotlight-fuzzy-ctx-iter-0-fuzzy-filtering-2026-06-13.md)

## ✋ Manual Testing Gate — Iteration 0

> STOP. Do not proceed to Iteration 1 until every item is confirmed.

- [x] Launch the spotlight overlay; type `sw` and observe `switch` appears (fuzzy root-keyword match, not just prefix).
- [x] In a branch-name slot, type a non-prefix subsequence (e.g. `mn` for `main`) and observe it surfaces ranked first.
- [x] Type a fragment with no subsequence match (e.g. `zzqq`) and observe an empty list, no crash.
- [x] Existing prefix-style typing still works: typing the start of a keyword still shows it.

**Confirmed by user:** 2026-06-13
**How to confirm:** Check every box, then reply "Iteration 0 confirmed" or describe what failed.

### Implementation Ledger — Iteration 0
- `test_subsequence_matches_with_gaps`: red → green ✓
- `test_empty_needle_scores_neutral_and_keeps_all`: red → green ✓
- `test_contiguous_run_outranks_scattered`: red → green ✓
- `test_start_of_string_outranks_late_start`: red → green ✓
- `test_word_start_match_is_boosted`: red → green ✓
- `test_filter_sorts_best_first_with_stable_tiebreak`: red → green ✓
- `test_filter_drops_non_matches`: red → green ✓
- `test_parser_surfaces_non_prefix_subsequence`: red → green ✓
- `test_parser_keeps_filter_text_raw`: red → green ✓
- `test_parser_ranks_best_candidate_first`: red → green ✓

### Iteration 1 — Auto-commit on a unique match
**Context file:** [Iteration 1 context](autobot-spotlight-fuzzy-ctx-iter-1-auto-commit-2026-06-13.md)

## ✋ Manual Testing Gate — Iteration 1

> STOP. Do not proceed past this until every item is confirmed.

- [x] Type a fragment that matches exactly one candidate; observe the field auto-rewrites to the full token followed by a space.
- [x] Type a fragment matching >1 candidate (e.g. `ma` with both `main` and `master` present); observe the field is NOT rewritten and you can keep typing.
- [x] After an auto-commit on a mid-command slot, observe the next slot's candidates appear.
- [x] Regression: a non-prefix subsequence in a slot (e.g. `mn` for `main`) still surfaces the match ranked first (Iteration 0 behaviour intact).

**Confirmed by user:** 2026-06-13
**How to confirm:** Check every box, then reply "Iteration 1 confirmed" or describe what failed.

### Implementation Ledger — Iteration 1
- `test_should_autocommit_returns_row_for_unique`: red → green ✓
- `test_should_autocommit_returns_none_when_ambiguous_or_empty`: red → green ✓
- `test_unique_match_rewrites_field_to_token_plus_space`: red → green ✓
- `test_ambiguous_fragment_does_not_rewrite`: red → green ✓
- `test_empty_fragment_does_not_rewrite`: red → green ✓
- `test_exact_full_token_with_longer_candidate_does_not_rewrite`: red → green ✓
- `test_auto_commit_advances_to_next_slot`: red → green ✓
- `test_no_infinite_recursion_on_auto_commit`: red → green ✓

