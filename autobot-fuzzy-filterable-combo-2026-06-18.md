<!-- autobot-status
stage: 1
iteration: -
gate: none
updated: 2026-06-18
-->

# Autobot — Fuzzy search + highlighting in FilterableComboBox

## Feature

Make [FilterableComboBox](worktree-manager/worktree_manager/ui/filterable_combo.py) filter and
highlight exactly the way [spotlight_overlay.py](worktree-manager/worktree_manager/ui/spotlight_overlay.py)
does:

- **Fuzzy (subsequence) matching with relevance ranking**, replacing the current `QCompleter`
  `MatchContains` substring filter. Reuses [fuzzy_filter / fuzzy_match_indices](worktree-manager/worktree_manager/spotlight/fuzzy.py).
- **Per-character highlighting** of the matched chars in each popup row, via a rich-text
  `QStyledItemDelegate` mirroring spotlight's `_HighlightDelegate`.
- **Custom popup list** replacing `QCompleter` — a `QListView`/`QListWidget` we filter and render
  ourselves.
- The shared highlight helper (`build_row_html`) is **extracted into a shared UI module** that both
  the spotlight overlay and the combo import — no logic duplication.

The combo's existing **selection-only behavioural contract is preserved exactly**: value is always
one of the existing items; junk text flags invalid (red border) and does not change the committed
selection; `currentIndexChanged` fires once on a real commit and never while typing; `currentText()`
returns the committed item; arrow-key navigation moves the line edit without committing; Esc restores
the committed text.

### Decisions (locked with user before design)
- Match scope → **full fuzzy + ranking** (best-first, like spotlight).
- Popup → **custom popup list**, dropping `QCompleter`.
- Code reuse → **reuse `spotlight.fuzzy`** + extract `build_row_html` into a shared UI helper.

### Consequence to flag
The current test suite hard-codes the `QCompleter` contract
([test_filterable_combo_qt.py](worktree-manager/tests/test_filterable_combo_qt.py):
`test_filterable_combo_has_completer`, `test_completer_uses_contains_filter`,
`test_completer_is_case_insensitive`, `test_addItems_keeps_completer_in_sync`; and
[test_filterable_combo_completer_emit_qt.py](worktree-manager/tests/test_filterable_combo_completer_emit_qt.py)
which drives commits through `_on_completer_activated`). Dropping `QCompleter` means these
completer-specific tests are **migrated** to the new custom-popup contract while keeping every
*behavioural* guarantee (commit-once, revert-on-junk, no-signal-while-typing, arrow nav, Esc
restore). New behaviour (fuzzy ranking, highlight HTML) gets new tests.

## Frontend Design

The widget still *looks* like a normal combo box when collapsed. The change is visible only when the
popup is open: rows are fuzzy-matched, ranked best-first, and the matched characters are highlighted
in the accent colour (the same `#4da3ff` bold spans spotlight uses).

### Collapsed (resting) state — unchanged from today
```
┌─ Base branch ───────────────┐
│ feature/login             ▾ │
└─────────────────────────────┘
```

### Filtering — user types "flog"; fuzzy popup with highlighting
```
┌─ Base branch ───────────────┐
│ flog▌                     ▾ │   ← typed "flog" (fuzzy subsequence, case-insensitive)
├─────────────────────────────┤
│ [f][l]ist-pages             │   ← matched chars f,l,o,g highlighted in accent bold
│ [f]eature/[log]in           │   ← ranked best-first by fuzzy_score
│ re[f]actor/f[l]a[g]s        │
└─────────────────────────────┘
   (only fuzzy matches shown; non-matches like "main" hidden)
   [x] = highlighted (accent #4da3ff, bold) matched character
```

### Keyboard navigation — Down highlights next row, line edit previews it (no commit)
```
┌─ Base branch ───────────────┐
│ feature/login             ▾ │   ← Down pressed: line edit previews highlighted row
├─────────────────────────────┤
│   [f]eature/[log]in         │
│ ▶ re[f]actor/f[l]a[g]s      │   ← current row (selected); not committed yet
└─────────────────────────────┘
   Enter commits this row · Esc restores committed text · index unchanged until commit
```

### Committed — user picks a row (click / Enter)
```
┌─ Base branch ───────────────┐
│ refactor/flags            ▾ │   ← value committed; currentIndexChanged fires ONCE
└─────────────────────────────┘
```

### No-match / invalid — typed junk that fuzzy-matches nothing, then blur/Enter
```
typed:  ┌─────────────────────┐        on blur:  ┌─────────────────────┐
        │ zzqqww            ▾ │   ───────────▶   │ zzqqww            ▾ │
        ├─────────────────────┤                  └─────────────────────┘
        │  (no matches)       │                    (red invalid border;
        └─────────────────────┘                     committed selection UNCHANGED,
          empty fuzzy result                         listeners NOT notified)
```

### Empty needle — popup shows all items in model order (no ranking, no highlight)
```
┌─ Base branch ───────────────┐
│ ▌                         ▾ │   ← field cleared / just focused
├─────────────────────────────┤
│ feature/login               │   ← all items, original order, no highlight
│ feature/search              │
│ refactor/flags              │
│ main                        │
└─────────────────────────────┘
```

### Clarifying questions
1. **Popup trigger when collapsed** — today clicking the arrow shows the full native combo popup.
   Should the *fuzzy* popup open on focus/click too (showing all items, empty-needle), or only once
   the user starts typing? (I've assumed: opens showing all items on focus, same as a normal combo,
   and narrows as you type.)
2. **Highlight colour** — reuse spotlight's exact `#4da3ff` accent, or pull from the app theme/
   palette so it matches the combo's own styling? (I've assumed: reuse the shared `HIGHLIGHT_COLOR`
   so spotlight and combo stay visually identical, which is the point of the feature.)
3. **Ranking visibility** — full fuzzy ranking reorders rows by relevance (so the list order changes
   as you type). Confirm that re-ordering is desired here (it is the spotlight behaviour); the only
   alternative we discussed and rejected was preserving model order.
