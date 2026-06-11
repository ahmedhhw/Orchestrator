<!-- autobot-status
stage: 7
iteration: 3
gate: confirmed
updated: 2026-06-10
-->

# Autobot — UI fixes & dropdown/worktree bug debugging

Feature bundle (5 items):
1. Force the app to stay in **light mode**.
2. **Dropdown activation bug (Bug A)** — selecting an item in a `FilterableComboBox` via the completer popup sometimes does not fire `currentIndexChanged`, so downstream handlers (e.g. Command Center worktree switch) never react.
3. **Worktree-switch duplicate-pane bug (Bug B)** — switching a worktree in Command Center destroys the running pane and launches a new run; intermittently this leaves a duplicate/leaked pane. Intended behaviour (confirmed): restart in the new worktree, but guarantee **exactly one** pane results.
4. **Worktree dirty indicator** — show in the per-repo worktree list whether each worktree has uncommitted changes.
5. **Diff line wrapping** — wrap long lines in the diff hunk view instead of clipping.

**Test runner:** `python3.14 -m pytest` (project convention).

---

## Root-cause analysis (debugging, items 2 & 3)

### Bug A — swallowed `currentIndexChanged` in FilterableComboBox

In [filterable_combo.py](worktree_manager/ui/filterable_combo.py):

- [`_on_text_edited`](worktree_manager/ui/filterable_combo.py#L32) sets `_in_edit = True` and calls `blockSignals(True)` the moment you type to filter.
- Picking an item from the completer popup invokes [`_commit_from_completer`](worktree_manager/ui/filterable_combo.py#L37). The popup, as a side effect, can already move `currentIndex` **while signals are blocked**.
- `_commit_from_completer` then only calls `setCurrentIndex(idx)` **if `currentIndex() != idx`** (line 42). When the index already matches, the call is skipped — so the change happened entirely under `blockSignals(True)` and **`currentIndexChanged` never emits**.

Downstream, [`CommandPane._on_wt_combo_changed`](worktree_manager/ui/command_pane.py#L396) is wired to `currentIndexChanged` ([command_pane.py:249](worktree_manager/ui/command_pane.py#L249)). If the signal is swallowed, the worktree switch never fires → "switching the dropdown doesn't activate it". The same combo feeds the per-repo branch switcher ([per_repo_worktrees_view.py:225](worktree_manager/ui/per_repo_worktrees_view.py#L225)).

**Fix direction:** make a committed selection from the completer emit deterministically. Re-emit `currentIndexChanged` on commit even when the index value already matches, by forcing the emission through a controlled path rather than guarding on equality while signals were blocked.

### Bug B — worktree switch always destroys + relaunches

In [`CommandCenterPanel._change_worktree`](worktree_manager/ui/command_center_panel.py#L184): it calls [`remove_pane`](worktree_manager/ui/command_center_panel.py#L145) then [`self._vm.launch(...)`](worktree_manager/ui/command_center_panel.py#L189) — i.e. every worktree switch kills the pane and starts a brand-new run. The duplicate/leak is intermittent because it's coupled to Bug A's signal timing: when the change fires you get destroy+recreate (looks like a swap); when an extra/late signal fires you can get a second `launch`, producing a duplicate pane.

**Intended behaviour (confirmed with user):** keep the restart-in-new-worktree design, but make `_change_worktree` idempotent so exactly one pane exists afterward — guard against re-entrant/duplicate invocation.

---

## Frontend Design

Only items 1, 4, 5 have a visible UI surface. Items 2 & 3 are behavioural (no new UI).

### Item 1 — Light mode (no new UI, global appearance)
The whole app renders with the light palette regardless of the OS dark-mode setting. No new widget; the macOS dark background/borders no longer appear.

### Item 4 — Worktree dirty indicator (per-repo worktree list)

Current row ([per_repo_worktrees_view.py:169](worktree_manager/ui/per_repo_worktrees_view.py#L169)):
```
○  feature-login        2h ago   [ branch ▾ ]  🖊  ✕
●  (main)               5m ago   [ main   ▾ ]
```

With dirty indicator (a marker appears only when the worktree has uncommitted changes):
```
○  feature-login  ●     2h ago   [ branch ▾ ]  🖊  ✕      ← dirty (orange ● after name)
●  (main)               5m ago   [ main   ▾ ]            ← clean, no marker
○  wip-refactor   ●     1d ago   [ branch ▾ ]  🖊  ✕      ← dirty
```
- Dirty marker: a small orange `●` placed right after the worktree name, with tooltip "Uncommitted changes".
- Clean worktrees show nothing extra (no marker, no layout shift beyond the marker's own slot).

### Item 5 — Diff line wrapping (diff hunk view)

Current — long lines clip / require horizontal scroll ([diff_hunk_view.py:159](worktree_manager/ui/diff_hunk_view.py#L159)):
```
+ this is a really long added line that runs off the right edge and gets cli…
```

With wrapping — the line wraps within the view width:
```
+ this is a really long added line that runs off the right edge
  and now wraps onto the next visual row instead of clipping
```
- Each diff line `QLabel` wraps (`setWordWrap(True)`); the `+`/`-` background colour spans all wrapped rows.
- The per-line monospace font and padding are unchanged.

### Clarifying questions
- Item 4: orange `●` after the name acceptable, or do you prefer a different glyph/position (e.g. a `*` suffix, or a coloured name)? Default in mocks: orange `●`.
- Item 5: wrap unconditionally, or behind a toggle? Default: unconditional wrapping (simpler; matches "add line wrapping").

---

## Backend Design

### Item 1 — Force light mode
Set the application colour scheme to Light at startup, in [cli.py](worktree_manager/cli.py#L1038) right after the `QApplication` is created:
```
qt_app = QApplication.instance() or QApplication(sys.argv)
qt_app.styleHints().setColorScheme(Qt.ColorScheme.Light)   # PySide6 ≥ 6.8
```
- **API verified (2026-06-10):** installed PySide6 is **6.11.1**; both `Qt.ColorScheme.Light` and `QStyleHints.setColorScheme` exist. The one-liner is sufficient — no `QPalette` fallback needed.

### Item 2 — Bug A fix (deterministic emit on commit)
In [`FilterableComboBox`](worktree_manager/ui/filterable_combo.py), change `_commit_from_completer` so a completer selection always produces a `currentIndexChanged` emission for the chosen index:
```
_commit_from_completer(text):
    idx = findText(text)
    _end_edit()                     # unblocks signals
    if idx >= 0:
        _committed_index = idx
        if currentIndex() == idx:
            # value already moved under blockSignals -> emit was lost; re-emit
            currentIndexChanged.emit(idx)
        else:
            setCurrentIndex(idx)    # normal path emits
```
Invariant: exactly one `currentIndexChanged(idx)` per committed selection, never zero, never on raw keystrokes.

### Item 3 — Bug B fix (single pane after switch)
Make [`_change_worktree`](worktree_manager/ui/command_center_panel.py#L184) idempotent/guarded so one switch → exactly one new pane:
```
_change_worktree(handle, new_path):
    run_id = handle.run_id
    if run_id in self._switching:      # re-entry guard
        return
    self._switching.add(run_id)
    try:
        remove_pane(run_id)            # exactly once
        self._vm.launch(... worktree_path=new_path ...)
    finally:
        self._switching.discard(run_id)
```
- Removes the silent `except Exception: pass` at [command_center_panel.py:196](worktree_manager/ui/command_center_panel.py#L196) — surface launch failures (project rule: no silent exceptions).

### Item 4 — Dirty state in worktree view data
Reuse [`GitService.has_uncommitted_changes`](worktree_manager/git_service.py#L128). Compute dirty per worktree inside the existing background loop in [`load_worktree_view_data`](worktree_manager/main_window_vm.py#L179) (runs off the UI thread via `BackgroundJob`):
```
load_worktree_view_data:
    for wt in worktrees:
        dirty_map[wt.path] = git.has_uncommitted_changes(wt.path)
        on_progress(...)
    return {worktrees, branch_status, dirty: dirty_map}
```
- Add `is_dirty: bool = False` to [`WorktreeModel`](worktree_manager/models.py#L4) OR carry a `dirty` map in the returned dict. **Decision in Stage 2** — leaning toward `WorktreeModel.is_dirty` so the row builder reads `wt.is_dirty` directly.
- [`_add_row`](worktree_manager/ui/per_repo_worktrees_view.py#L169) renders the orange `●` when dirty.

### Item 5 — Diff line wrapping
In [`diff_hunk_view`](worktree_manager/ui/diff_hunk_view.py#L159), set `lbl.setWordWrap(True)` on each diff-line label. Verify the `+`/`-` background spans wrapped rows and the horizontal scrollbar is no longer needed.

### API / dependency verification (to run in Stage 2/iteration 0)
- Confirm installed PySide6 version and that `Qt.ColorScheme.Light` + `QStyleHints.setColorScheme` exist.

---

## Iteration Plan

- Iteration 0 — Force light mode
- Iteration 1 — Worktree dirty indicator
- Iteration 2 — Diff line wrapping
- Iteration 3 — Dropdown + worktree-switch bug fixes (Bug A + Bug B)

### Iteration 0 — Force light mode
**Context file:** [Iteration 0 context](autobot-ui-fixes-ctx-iter-0-light-mode-2026-06-10.md)

### Implementation Ledger — Iteration 0
- `test_force_light_mode_sets_color_scheme`: red → green ✓

## ✋ Manual Testing Gate — Iteration 0

> STOP. Do not proceed to Iteration 1 until every item is confirmed.

- [x] Launch the app on a Mac in OS dark mode — the app renders with a light background/light controls.
- [x] Toggle the OS appearance to light and back to dark while the app is open — the app stays light.

**Confirmed by user:** 2026-06-10
**How to confirm:** Check every box, then reply "Iteration 0 confirmed" or describe what failed.

### Iteration 1 — Worktree dirty indicator
**Context file:** [Iteration 1 context](autobot-ui-fixes-ctx-iter-1-dirty-indicator-2026-06-10.md)

### Implementation Ledger — Iteration 1
- `test_worktree_model_is_dirty_defaults_to_false`: red → green ✓
- `test_load_worktree_view_data_marks_dirty_worktrees`: red → green ✓
- `test_load_worktree_view_data_calls_dirty_check_once_per_worktree`: red → green ✓
- `test_dirty_worktree_row_contains_dirty_marker`: red → green ✓
- `test_clean_worktree_row_has_no_dirty_marker`: red → green ✓

## ✋ Manual Testing Gate — Iteration 1

> STOP. Do not proceed to Iteration 2 until every item is confirmed.

- [x] In a repo with one dirty worktree and one clean, the dirty one shows an orange ● after its name; the clean one shows none.
- [x] Hovering the ● shows tooltip "Uncommitted changes".
- [x] Commit/stash the changes and refresh — the marker disappears.
- [x] Regression: app still launches in light mode and worktrees load normally.

**Confirmed by user:** 2026-06-10
**How to confirm:** Check every box, then reply "Iteration 1 confirmed" or describe what failed.

### Iteration 2 — Diff line wrapping
**Context file:** [Iteration 2 context](autobot-ui-fixes-ctx-iter-2-diff-wrap-2026-06-10.md)

### Implementation Ledger — Iteration 2
- `test_diff_line_labels_have_word_wrap_enabled`: red → green ✓
- `test_word_wrap_does_not_remove_added_or_removed_styling`: red → green ✓

## ✋ Manual Testing Gate — Iteration 2

> STOP. Do not proceed to Iteration 3 until every item is confirmed.

- [x] Open a diff with a line longer than the view width — it wraps onto multiple rows instead of clipping.
- [x] The added/removed background colour covers the whole wrapped line.
- [x] No horizontal scrollbar is needed for long lines.
- [x] Regression: dirty indicator and light mode still work; short diff lines render unchanged.

**Confirmed by user:** 2026-06-10
**How to confirm:** Check every box, then reply "Iteration 2 confirmed" or describe what failed.

### Iteration 3 — Dropdown + worktree-switch bug fixes (Bug A + Bug B)
**Context file:** [Iteration 3 context](autobot-ui-fixes-ctx-iter-3-dropdown-switch-fix-2026-06-10.md)
**Reviewed plan:** [Iteration 3 plan](autobot-ui-fixes-plan-iter-3-dropdown-switch-fix-2026-06-10.md)

### Implementation Ledger — Iteration 3
- Phase 3.1
  - `test_first_filter_keystroke_records_the_starting_index`: red → green ✓
  - `test_index_before_edit_is_not_overwritten_by_later_keystrokes`: red → green ✓
- Phase 3.2
  - `test_committing_a_match_after_the_index_moved_emits_once`: red → green ✓
  - `test_committing_a_match_on_the_normal_path_emits_once`: red → green ✓
  - `test_committing_the_already_selected_item_emits_nothing`: red → green ✓
  - `test_typing_filter_text_without_committing_emits_nothing`: red → green ✓
- Phase 3.3
  - `test_switching_a_worktree_leaves_exactly_one_pane`: red → green ✓
  - `test_a_concurrent_switch_for_the_same_run_is_ignored`: red → green ✓
  - `test_a_fresh_switch_after_one_completes_is_allowed`: red → green ✓
- Phase 3.4
  - `test_a_duplicate_run_on_switch_is_logged_not_swallowed`: red → green ✓
  - `test_an_unexpected_launch_error_on_switch_propagates`: red → green ✓

## ✋ Manual Testing Gate — Iteration 3

> STOP. This is the last iteration; do not declare done until every item is confirmed.

- [x] In Command Center, switch a running command's worktree via the dropdown — it actually re-activates in the new worktree (Bug A fixed).
- [x] After switching, there is exactly ONE pane for that command — no duplicate, no disappearance (Bug B fixed).
- [x] Rapidly switching the worktree dropdown does not spawn extra panes.
- [x] Regression: the per-repo branch dropdown still switches branches on selection.
- [x] Regression: typing to filter the dropdown without picking does not trigger a switch.
- [x] Regression: dirty indicator, diff wrapping, and light mode all still work.

**Confirmed by user:** 2026-06-10
**How to confirm:** Check every box, then reply "Iteration 3 confirmed" or describe what failed.

---
📁 **Autobot files** · [main doc](worktree-manager/autobot-ui-fixes-2026-06-10.md)
