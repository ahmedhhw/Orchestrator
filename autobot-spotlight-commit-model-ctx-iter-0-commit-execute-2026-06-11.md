# Context: Iteration 0 — Commit/execute overlay with nickname fix, mouse, invalid-flag & caption

## Goal
Rebuild [spotlight_overlay.py](worktree-manager/worktree_manager/ui/spotlight_overlay.py) around a single
`parse()`-driven Enter/click rule, replacing the ghost-text / Tab-cycle machinery. This one iteration
delivers the whole behavioural core: commit-or-execute on Enter, the **nickname execution fix** (the
"Unknown command" bug), single-click mouse parity, the red `invalid` flag for unmatched text, and a list
caption naming the active slot. Committed tokens stay as plain text in the line edit — **no chips yet** (that
is Iteration 1).

## Tests to write
- shows root keywords and MRU on empty input with row 0 highlighted: the list populates and `currentRow()==0`.
- typing filters the active token: list narrows, line-edit text unchanged otherwise.
- up/down moves the highlight without committing or changing the typed text.
- enter on a highlighted keyword row commits it as a token with a trailing space and advances the list.
- enter walking every slot of a multi-slot command commits each, then executes with all committed args.
- enter on a complete zero-slot keyword command executes it with empty args and hides the overlay.
- enter on an exact nickname runs the stored action with stored args and hides (the bug fix).
- single click on a list row commits it exactly like enter on that row.
- single click on a row that completes the command executes it.
- enter (or click) on unmatched free-typed text flags the input invalid, keeps the text, runs nothing, shows an error.
- typing after an error clears the error.
- escape hides the overlay.
- tab does nothing (no commit, no cycle, text unchanged).
- caption reads COMMANDS on the root/keyword stage and the slot's friendly plural on a slot stage; hidden when the list is empty.

## Files to touch
- [spotlight_overlay.py](worktree-manager/worktree_manager/ui/spotlight_overlay.py) — rewrite: remove
  `_GhostLineEdit`, `_commit_ghost`, `_handle_tab`, `_tab_suffix`, `_longest_common_prefix`, the `_tab_cycle`
  field and all ghost branches; plain `QLineEdit`; new `parse`-driven Enter/click rule; add a caption label
  above the list; single-click handling on the list.
- [test_spotlight_overlay_qt.py](worktree-manager/tests/test_spotlight_overlay_qt.py) — delete/rewrite the
  ghost/Tab tests (`test_enter_with_ghost_*`, every `test_tab_*`, every `test_ghost_text_*`,
  `test_non_tab_key_does_not_commit_ghost`); keep & re-express the survivors against the new model; add the
  new tests above.

## Design / pseudocode

#### `worktree_manager/ui/spotlight_overlay.py`
```
# Widget tree (top→bottom): QLineEdit (active token), caption QLabel, QListWidget, error QLabel.
# State: the line edit's text IS the input string. Everything derives from parse(text).

SLOT_CAPTIONS = {"repo": "REPOS", "worktree": "WORKTREES", "branch": "BRANCHES",
                 "cmd": "COMMANDS", "name": "PROJECTS", "editor": "EDITORS"}

on text changed:
    clear error; refresh(text)

refresh(text):
    r = parse(text)
    list.clear(); add r.suggestions; if any -> setCurrentRow(0)
    render_caption(r)

render_caption(r):
    if not r.suggestions:                 caption.hide(); return
    if r.action is None:                  cap = "COMMANDS"
    elif r.slot_index < len(r.action.slots):
        name = r.action.slots[r.slot_index].name
        cap = SLOT_CAPTIONS.get(name, name.upper())
    else:                                 cap = "COMMANDS"
    caption.setText(cap); caption.show()

# The single Enter/click rule:
commit_or_execute():
    r = parse(text)
    # 1. exact nickname -> execute stored action (THE BUG FIX)
    if r.completion_kind == "nickname" and r.nickname_action_name:
        spec = registry.get_by_name(r.nickname_action_name)
        if spec is None: set_error("Unknown command"); return
        spec.runner(dict(r.nickname_args or {}))
        on_action_executed?(r.nickname_action_name, args); hide(); return
    # 2. complete command -> execute
    if r.action and r.executable and (not r.action.slots or r.slot_index == len(r.action.slots)):
        spec.runner(dict(r.committed_args)); on_action_executed?; hide(); return
    # 3. incomplete + a row highlighted -> commit that row, advance
    item = list.currentItem()
    if r.suggestions and item is not None:
        text = commit(text, item.text()); refresh(text); return
    # 4. nothing to commit -> flag invalid, keep text, run nothing
    set_invalid(True); set_error("No matching option"); return

commit(text, row):
    base = text without its trailing r.filter_text   # strip the active partial
    return base + row + " "

# events: Enter -> commit_or_execute(); list itemClicked -> set currentItem then commit_or_execute();
#         Up/Down -> move list currentRow only; Escape -> hide(); Tab -> ignore (return True, do nothing).

set_invalid(flag): line_edit.setProperty("invalid", flag); unpolish/polish   # mirror filterable_combo
```

## Relevant existing code

**Parser contract** — `parse(text) -> ParseResult` (UNCHANGED, do not edit
[action_parser.py](worktree-manager/worktree_manager/spotlight/action_parser.py)):
```python
@dataclass
class ParseResult:
    action: ActionSpec | None
    suggestions: list[str]
    filter_text: str = ""
    executable: bool = False
    completion_kind: str = "keyword"     # "keyword" | "slot" | "nickname"
    committed_args: dict[str, str] = field(default_factory=dict)
    slot_index: int = 0
    all_candidates: list[str] = field(default_factory=list)
    nickname_action_name: str | None = None   # set iff input exactly matches a nickname
    nickname_args: dict | None = None
```
Key behaviours already provided by the parser:
- empty text → MRU labels then root keywords in `suggestions`.
- exact nickname (single token, no trailing space) → `completion_kind=="nickname"`, `executable=True`,
  `nickname_action_name`/`nickname_args` set.
- all slots committed → `executable=True`, `slot_index == len(action.slots)`, `committed_args` full.
- a slot stage → `slot_index` = active slot, `committed_args` = earlier slots, `suggestions` filtered by
  `filter_text`.

**Registry** — [action_registry.py](worktree-manager/worktree_manager/spotlight/action_registry.py)
(UNCHANGED):
```python
@dataclass
class ArgSlot:
    name: str
    candidates: Callable[[dict], list[str]]

@dataclass
class ActionSpec:
    name: str
    keywords: list[str]
    slots: list[ArgSlot] = field(default_factory=list)
    runner: Callable[[dict], None] = field(default=lambda args: None)
    description: str = ""

class ActionRegistry:
    def register(self, spec): ...
    def root_keywords(self) -> list[str]: ...
    def get_by_name(self, name) -> ActionSpec | None: ...
    # plus next_keywords / find_longest_keyword_match used only by the parser
```

**Current overlay constructor / public API to preserve** (from
[spotlight_overlay.py](worktree-manager/worktree_manager/ui/spotlight_overlay.py)):
```python
class SpotlightOverlay(QWidget):
    def __init__(self, parser: ActionParser, parent=None, on_action_executed=None): ...
    def error_text(self) -> str: ...          # tests read this
    def show_centered_over(self, parent): ...  # clears text, refreshes, focuses the edit, shows
    # frameless window flags must stay (test_overlay_is_frameless)
```

**Existing test helpers** to reuse/adapt (in
[test_spotlight_overlay_qt.py](worktree-manager/tests/test_spotlight_overlay_qt.py)):
```python
def _make_overlay(qtbot, projects=("alpha","beta","gamma")): ...   # builds registry+parser+overlay
def _list_items(overlay): ...                                      # reads the QListWidget rows
```

## Constraints / invariants
- **Parser/registry/store are not edited.** This is overlay-only.
- Enter/click is decided ONLY by `parse(text)` — never any ghost/MRU side-state.
- The line-edit text is the sole source of truth; caption + list always derive from `parse(text)`.
- No silent excepts: an unknown action / missing spec surfaces the error label, never `except: pass`
  (see [[feedback_no_silent_exceptions]]).
- `set_invalid` mirrors filterable_combo exactly: dynamic `invalid` property + unpolish/polish; the typed
  text is kept, never reverted.
- Committed tokens are PLAIN TEXT in the line edit this iteration. No chips, no chip bar, no click-to-jump,
  no flow-layout/overflow — all of that is Iteration 1.
- `commit()` strips the trailing `filter_text` then appends `row + " "` so the next slot becomes active.

## Done when (gate items)
- [ ] Ctrl+K shows MRU then root keywords, row 0 highlighted, caption `COMMANDS`.
- [ ] Typing filters; Up/Down + hover move highlight without committing or changing text.
- [ ] Enter on a highlighted row commits it (plain text + trailing space); list + caption advance (REPOS, WORKTREES, …).
- [ ] Full multi-slot command: last slot committed → list empties → Enter executes → overlay closes.
- [ ] Zero-slot keyword command executes on Enter once its keyword is complete.
- [ ] Exact nickname + Enter runs the stored action with stored args and closes — no "Unknown command".
- [ ] Single-click a row commits/executes it exactly as Enter would.
- [ ] Invalid text + Enter → red `invalid` border, text kept, nothing runs, error line shown.
- [ ] Escape closes the overlay.
- [ ] Tab does nothing.

## TDD mode: Autonomous
