# Context: Iteration 2 — Diff line wrapping

## Goal
Wrap long lines in the diff hunk view so they wrap within the view width instead of clipping / requiring horizontal scroll. The `+`/`-` background colour spans all wrapped rows.

## Tests to write
- Diff line labels enable word wrap: after rendering hunks, each diff-line label (objectName "diff_line") has `wordWrap()` True.
- Wrapping does not break the +/- styling: an added line label still carries the added background style; a removed line still carries the removed style (i.e. wrap is additive, styling unchanged).

## Files to touch
- [diff_hunk_view.py](worktree_manager/ui/diff_hunk_view.py) — set `setWordWrap(True)` on each diff-line `QLabel` in the render loop ([diff_hunk_view.py:159](worktree_manager/ui/diff_hunk_view.py#L159)).

## Design / pseudocode

#### `worktree_manager/ui/diff_hunk_view.py`
```
for line in hunk.lines:
    lbl = QLabel(line if line else " ")
    lbl.setObjectName("diff_line")
    lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lbl.setFont(self._monospace_font())
    lbl.setWordWrap(True)          # NEW — wrap instead of clip
    ... existing +/- styling unchanged ...
```

## Relevant existing code
[diff_hunk_view.py:159-171](worktree_manager/ui/diff_hunk_view.py#L159):
```
for line in hunk.lines:
    lbl = QLabel(line if line else " ")
    lbl.setObjectName("diff_line")
    lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lbl.setFont(self._monospace_font())
    if line.startswith("-"):
        lbl.setStyleSheet(f"background-color: {_REMOVED_BG}; color: #ff8080; padding: 0 4px;")
    elif line.startswith("+"):
        lbl.setStyleSheet(f"background-color: {_ADDED_BG}; color: #80ff80; padding: 0 4px;")
    else:
        lbl.setStyleSheet("padding: 0 4px;")
    self._content_layout.insertWidget(pos, lbl)
    pos += 1
```
Scroll area uses `setWidgetResizable(True)` ([diff_hunk_view.py:45](worktree_manager/ui/diff_hunk_view.py#L45)) — so wrapped labels reflow to the viewport width automatically.

## Constraints / invariants
- Monospace font and `padding: 0 4px` unchanged.
- `+`/`-` background must span the full wrapped block (QLabel background does this natively once wrap is on).
- Header labels (hunk headers) are out of scope — only diff content lines wrap.

## Done when (gate items)
- [ ] Open a diff containing a line longer than the view width — it wraps onto multiple visual rows instead of clipping.
- [ ] The added/removed background colour covers the whole wrapped line.
- [ ] No horizontal scrollbar is needed for long lines.

## TDD mode: <Reviewed | Autonomous>
