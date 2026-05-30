# Filterable / Searchable Dropdowns

## Overview
Every dropdown in the worktree-manager app is currently a plain, non-editable `QComboBox`.
For dropdowns with many entries (branch pickers, repo pickers, worktree pickers) finding the
right item means scrolling a long popup. This feature replaces every `QComboBox` with a single
reusable drop-in widget, `FilterableComboBox`, that lets the user **type to filter** the list
inline (case-insensitive, matching anywhere in the text) while still behaving exactly like a
normal combo box for selection: the value can only ever be one of the existing items, and if the
user types something that doesn't match, the box reverts to its previous selection. Because it is
a behaviour-preserving drop-in, every existing dropdown becomes searchable with no change to the
code that populates it or listens to it.

## UI / Flow

**Default (collapsed) state — looks like today's dropdown:**
```
┌─ Base branch ───────────────┐
│ feature/login             ▾ │
└─────────────────────────────┘
```

**Filtering state — user clicks/focuses and types; popup shows only matches:**
```
┌─ Base branch ───────────────┐
│ ea▌                       ▾ │   ← user typed "ea" (matches anywhere, case-insensitive)
├─────────────────────────────┤
│ feature/login               │
│ feature/search-combo        │
│ refactor/feature-flags      │
└─────────────────────────────┘
```

**Committed state — user picks a match (click / Enter):**
```
┌─ Base branch ───────────────┐
│ feature/search-combo      ▾ │   ← value committed; listeners notified once
└─────────────────────────────┘
```

**No-match / revert state — user types junk then leaves the field (focus out / Esc):**
```
typed:  ┌─────────────────────┐        on blur:  ┌─────────────────────┐
        │ zzzqqq            ▾ │   ───────────▶   │ feature/login     ▾ │
        └─────────────────────┘                  └─────────────────────┘
          (no item matches)                        (reverts to last valid selection;
                                                     listeners NOT notified)
```

## Architecture

A new module introduces one widget, `FilterableComboBox`, that subclasses `QComboBox`. Every site
that constructs a `QComboBox` swaps in `FilterableComboBox` — `addItems`, `setCurrentText`,
`setCurrentIndex`, `findText`, `findData`, `itemData`, `currentData`, and `currentIndexChanged`
all keep their existing meaning.

**Signal choice — `currentIndexChanged`, not `currentTextChanged`.** On an editable combo,
`currentTextChanged` fires on every keystroke, whereas `currentIndexChanged` fires *only* on a
real index change (whether user- or programmatically-driven) and never while typing. So instead
of adding signal-suppression machinery inside the widget to tame keystroke noise, the few call
sites that currently listen to `currentTextChanged` are refactored to `currentIndexChanged`
(reading `currentText()` / `currentData()` in the slot where they need the value). This keeps the
widget tiny — just *editable + completer + revert-on-invalid-blur*, with **no signal suppression
code** — and is a true behavioural match: those handlers still fire on programmatic selection
during setup exactly as before. (`activated`/`textActivated` were rejected because they don't fire
on programmatic changes, which would break initial-population side effects such as auto-loading a
repo's branches.)

### Component view — one widget, many call sites

```mermaid
graph TD
    FCB["FilterableComboBox(QComboBox)<br/>worktree_manager/ui/filterable_combo.py<br/>(new)"]
    subgraph Panels
      MW["main_window.py:146"]
      PRW["per_repo_worktrees_view.py:199"]
      WPP["workspace_projects_panel.py:215"]
      WMP["worktree_management_panel.py:48"]
      BMP["branch_management_panel.py:477"]
      CP["command_pane.py:236"]
      DP["diff_panel.py:33, 41"]
    end
    subgraph Dialogs
      ACD["add_command_dialog.py:45"]
      LD["launch_dialog.py:159, 172"]
      POD["project_operations_dialog.py:59,193,206,517,615"]
      SP["settings_panel.py:48, 59"]
      CD["create_dialog.py:114, 130"]
    end
    MW --> FCB
    PRW --> FCB
    WPP --> FCB
    WMP --> FCB
    BMP --> FCB
    CP --> FCB
    DP --> FCB
    ACD --> FCB
    LD --> FCB
    POD --> FCB
    SP --> FCB
    CD --> FCB
```

### Behavioural contract — what the widget must guarantee

```mermaid
sequenceDiagram
    actor User
    participant LE as QLineEdit (combo edit)
    participant C as QCompleter (MatchContains, CI)
    participant FCB as FilterableComboBox
    participant Listener as Existing handler<br/>(currentIndexChanged)

    User->>LE: types "ea"
    LE->>C: filter list
    C-->>User: popup shows only matching items
    Note over Listener: index unchanged → NOT notified while typing

    alt picks a real item (click / Enter)
        User->>C: activate "feature/search-combo"
        C->>FCB: setCurrentIndex(match)
        FCB-->>Listener: currentIndexChanged fires ONCE
    else types non-matching text then leaves field
        User->>LE: editingFinished (blur / Esc)
        FCB->>FCB: findText fails → setCurrentIndex(committed) (same index)
        Note over Listener: index unchanged → NOT notified
    end
```

### Key facts established up front (PySide6 6.11 / Qt 6.11)
- An editable `QComboBox` emits `currentTextChanged` **on every keystroke**; `currentIndexChanged`
  only fires on a real index change. So the `currentTextChanged` handlers below are refactored to
  `currentIndexChanged`, which is keystroke-safe with no suppression code. The sites to refactor:
  [main_window.py:170](worktree-manager/worktree_manager/ui/main_window.py#L170),
  [per_repo_worktrees_view.py:222](worktree-manager/worktree_manager/ui/per_repo_worktrees_view.py#L222),
  [workspace_projects_panel.py:220](worktree-manager/worktree_manager/ui/workspace_projects_panel.py#L220),
  [launch_dialog.py:163](worktree-manager/worktree_manager/ui/launch_dialog.py#L163),
  [project_operations_dialog.py:63](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L63),
  [project_operations_dialog.py:536](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L536),
  [create_dialog.py:117](worktree-manager/worktree_manager/ui/create_dialog.py#L117), and
  [create_dialog.py:135](worktree-manager/worktree_manager/ui/create_dialog.py#L135). Each slot
  reads `currentText()` / `currentData()` for the value it needs. Sites already on
  `currentIndexChanged` (diff_panel, worktree/branch mgmt, command_pane, launch wt combo) are
  unchanged.
- `findData` / `currentData` / `itemData` / `setItemData` operate on the model and are unaffected
  by making the combo editable, so the userData-carrying combos
  ([diff_panel.py:33-43](worktree-manager/worktree_manager/ui/diff_panel.py#L33-L43),
  [worktree_management_panel.py:48](worktree-manager/worktree_manager/ui/worktree_management_panel.py#L48),
  [branch_management_panel.py:477](worktree-manager/worktree_manager/ui/branch_management_panel.py#L477),
  [command_pane.py:236](worktree-manager/worktree_manager/ui/command_pane.py#L236),
  [settings_panel.py:59](worktree-manager/worktree_manager/ui/settings_panel.py#L59)) keep working.
- `QCompleter` with `setFilterMode(Qt.MatchContains)`, `setCaseSensitivity(Qt.CaseInsensitive)`,
  `setCompletionMode(QCompleter.PopupCompletion)` gives the inline type-to-filter behaviour and
  must be re-pointed at the combo's model whenever items change.

### Existing files touched (replace `QComboBox()` → `FilterableComboBox()`, add import; plus refactor `currentTextChanged` → `currentIndexChanged` in the 8 sites listed above)
- [worktree-manager/worktree_manager/ui/main_window.py](worktree-manager/worktree_manager/ui/main_window.py)
- [worktree-manager/worktree_manager/ui/per_repo_worktrees_view.py](worktree-manager/worktree_manager/ui/per_repo_worktrees_view.py)
- [worktree-manager/worktree_manager/ui/workspace_projects_panel.py](worktree-manager/worktree_manager/ui/workspace_projects_panel.py)
- [worktree-manager/worktree_manager/ui/worktree_management_panel.py](worktree-manager/worktree_manager/ui/worktree_management_panel.py)
- [worktree-manager/worktree_manager/ui/branch_management_panel.py](worktree-manager/worktree_manager/ui/branch_management_panel.py)
- [worktree-manager/worktree_manager/ui/command_pane.py](worktree-manager/worktree_manager/ui/command_pane.py)
- [worktree-manager/worktree_manager/ui/diff_panel.py](worktree-manager/worktree_manager/ui/diff_panel.py)
- [worktree-manager/worktree_manager/ui/add_command_dialog.py](worktree-manager/worktree_manager/ui/add_command_dialog.py)
- [worktree-manager/worktree_manager/ui/launch_dialog.py](worktree-manager/worktree_manager/ui/launch_dialog.py)
- [worktree-manager/worktree_manager/ui/project_operations_dialog.py](worktree-manager/worktree_manager/ui/project_operations_dialog.py)
- [worktree-manager/worktree_manager/ui/settings_panel.py](worktree-manager/worktree_manager/ui/settings_panel.py)
- [worktree-manager/worktree_manager/ui/create_dialog.py](worktree-manager/worktree_manager/ui/create_dialog.py)

### New file
- `worktree-manager/worktree_manager/ui/filterable_combo.py` — the `FilterableComboBox` widget.

## Open Questions
_All resolved with the user before planning:_
- **Interaction style** → inline type-to-filter (editable combo + completer).
- **Free text** → selection-only; non-matching text reverts to the previous valid selection.
- **Scope** → every dropdown, via the uniform drop-in (small fixed-option combos such as the
  shell and editor pickers also become editable — harmless and consistent).

_Design notes (decided, not blocking):_
- Pressing **Esc** while filtering reverts the edit text and closes the popup (standard combo
  behaviour, preserved).
- Tiny fixed-option combos will now show a text cursor when focused; this is the accepted cost of
  applying the drop-in uniformly.

## Iteration Plan

### Iteration 0 — Walking Skeleton
**Delivers:** A `FilterableComboBox` exists, and the **Create Worktree → Base branch** dropdown is
searchable: the user can open that dialog, type to filter the branch list inline, pick a match,
and see junk text revert to the prior selection.
**Scope:**
- New widget `worktree-manager/worktree_manager/ui/filterable_combo.py` —
  `FilterableComboBox(QComboBox)`: editable + `QCompleter` (MatchContains, case-insensitive,
  popup); selection-only revert to the last committed item on `editingFinished`; completer model
  kept in sync when items change.
- Wire it into the base-branch combo at
  [create_dialog.py:114](worktree-manager/worktree_manager/ui/create_dialog.py#L114) (replace
  `QComboBox()` → `FilterableComboBox()`).
- Refactor that combo's signal at
  [create_dialog.py:117](worktree-manager/worktree_manager/ui/create_dialog.py#L117) from
  `currentTextChanged` → `currentIndexChanged`, with the slot reading `currentText()` to keep the
  existing `_base_var` two-way binding intact.
**Explicitly out of scope:** Every other dropdown in the app (still plain `QComboBox`); the
existing-branch combo in the same dialog; styling polish.

### Iteration 1 — Roll out to text-keyed dropdowns
**Delivers:** Every dropdown whose value is its display text becomes searchable, with their
`currentTextChanged` handlers moved to `currentIndexChanged`.
**Scope:**
- Branch combo at [main_window.py:146](worktree-manager/worktree_manager/ui/main_window.py#L146)
  (signal at [main_window.py:170](worktree-manager/worktree_manager/ui/main_window.py#L170)).
- [per_repo_worktrees_view.py:199](worktree-manager/worktree_manager/ui/per_repo_worktrees_view.py#L199)
  (signal at [:222](worktree-manager/worktree_manager/ui/per_repo_worktrees_view.py#L222)).
- [workspace_projects_panel.py:215](worktree-manager/worktree_manager/ui/workspace_projects_panel.py#L215)
  (signal at [:220](worktree-manager/worktree_manager/ui/workspace_projects_panel.py#L220)).
- [add_command_dialog.py:45](worktree-manager/worktree_manager/ui/add_command_dialog.py#L45)
  repo combo.
- [launch_dialog.py:159](worktree-manager/worktree_manager/ui/launch_dialog.py#L159) repo combo
  (signal at [:163](worktree-manager/worktree_manager/ui/launch_dialog.py#L163)).
- [project_operations_dialog.py:59](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L59)
  repo combo (signal at [:63](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L63)),
  the new-base / existing-branch combos at
  [:193](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L193) and
  [:206](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L206), and the per-row
  branch / base combos at
  [:517](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L517) (signal at
  [:536](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L536)) and
  [:615](worktree-manager/worktree_manager/ui/project_operations_dialog.py#L615).
- Shell combo at [settings_panel.py:48](worktree-manager/worktree_manager/ui/settings_panel.py#L48).
- Existing-branch combo at [create_dialog.py:130](worktree-manager/worktree_manager/ui/create_dialog.py#L130)
  (signal at [:135](worktree-manager/worktree_manager/ui/create_dialog.py#L135)).
**Builds on:** Iteration 0.

### Iteration 2 — Roll out to userData-keyed dropdowns
**Delivers:** The remaining dropdowns — those that carry `userData` (repo/worktree paths, editor
keys) and already use `currentIndexChanged` — become searchable, with `findData` / `currentData` /
`itemData` selection still working.
**Scope:**
- [diff_panel.py:33](worktree-manager/worktree_manager/ui/diff_panel.py#L33) repo combo and
  [:41](worktree-manager/worktree_manager/ui/diff_panel.py#L41) worktree combo.
- [worktree_management_panel.py:48](worktree-manager/worktree_manager/ui/worktree_management_panel.py#L48)
  repo combo.
- [branch_management_panel.py:477](worktree-manager/worktree_manager/ui/branch_management_panel.py#L477)
  repo combo.
- [command_pane.py:236](worktree-manager/worktree_manager/ui/command_pane.py#L236) worktree combo.
- [launch_dialog.py:172](worktree-manager/worktree_manager/ui/launch_dialog.py#L172) worktree combo.
- Editor combo at [settings_panel.py:59](worktree-manager/worktree_manager/ui/settings_panel.py#L59).
**Builds on:** Iterations 0 and 1.

## ✋ Manual Testing Gate — Iteration 0

> STOP. Do not proceed to Iteration 1 until every item below is checked off by the user.

- [ ] Launch the app and open the **Create Worktree** dialog.
- [ ] Click the **Base branch** dropdown — confirm it is now editable (a text cursor appears).
- [ ] Type a partial string (e.g. `fea` or `main`) — confirm a filtered popup appears showing only matching branches.
- [ ] Select a match from the popup — confirm the combo shows the chosen branch and no spurious errors appear.
- [ ] Type a string that matches nothing (e.g. `zzzzzzz`) then press Tab or click away — confirm the combo reverts to the previously selected branch.
- [ ] Proceed to create a worktree using the filtered selection — confirm the worktree is created on the correct branch (the widget did not pass bad data downstream).

**How to confirm:** Run `python3.14 run.py` from `worktree-manager/`, perform each action above, and check off each item manually.
Reply "Iteration 0 confirmed" (or describe any failures) before I write the plan for Iteration 1.
