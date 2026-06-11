# Context: Iteration 1 — Worktree dirty indicator

## Goal
Show, in the per-repo worktree list, whether each worktree has uncommitted changes — an orange `●` after the worktree name, tooltip "Uncommitted changes". Clean worktrees show no marker.

## Tests to write
- WorktreeModel carries a dirty flag defaulting to clean: a `WorktreeModel(...)` without `is_dirty` has `is_dirty == False`.
- load_worktree_view_data marks dirty worktrees: with a git service that reports one worktree dirty and one clean, the returned worktrees have `is_dirty` set correctly per path.
- load_worktree_view_data does not call the dirty check redundantly: `has_uncommitted_changes` is called once per worktree.
- The row shows a dirty marker only for dirty worktrees: building a row for a dirty worktree contains a visible dirty-marker label; a clean worktree's row does not.

## Files to touch
- [models.py](worktree_manager/models.py) — add `is_dirty: bool = False` to [WorktreeModel](worktree_manager/models.py#L4).
- [main_window_vm.py](worktree_manager/main_window_vm.py) — in [load_worktree_view_data](worktree_manager/main_window_vm.py#L179), set `wt.is_dirty` via the git dirty check inside the existing loop.
- [per_repo_worktrees_view.py](worktree_manager/ui/per_repo_worktrees_view.py) — in [_add_row](worktree_manager/ui/per_repo_worktrees_view.py#L169), add the orange `●` marker after the name when `wt.is_dirty`.

## Design / pseudocode

#### `worktree_manager/models.py`
```
@dataclass
class WorktreeModel:
    path: str
    branch: str
    is_main: bool
    last_commit_ts: int
    is_merged: bool
    is_stale: bool
    is_dirty: bool = False     # new, defaults clean
```

#### `worktree_manager/main_window_vm.py`
```
load_worktree_view_data(on_progress=None):
    worktrees = self.load_worktrees()
    branch_status = self.list_branches_with_checkout_status()
    for i, wt in enumerate(worktrees, 1):
        wt.is_dirty = self._git.has_uncommitted_changes(wt.path)
        if on_progress: on_progress(i, total, wt.branch)
    return {"worktrees": worktrees, "branch_status": branch_status}
```

#### `worktree_manager/ui/per_repo_worktrees_view.py`
```
_add_row(wt, branch_status):
    ... dot, name_label added ...
    if wt.is_dirty:
        dirty = QLabel("●")
        dirty.setObjectName("dirty_marker")
        dirty.setStyleSheet("color: orange;")
        dirty.setToolTip("Uncommitted changes")
        layout.addWidget(dirty)   # right after name_label
    ... age, stale, stretch, combo ...
```

## Relevant existing code
[GitService.has_uncommitted_changes](worktree_manager/git_service.py#L128):
```
def has_uncommitted_changes(self, worktree_path: str) -> bool:
    out = self._run(["git", "status", "--porcelain"], cwd=worktree_path)
    ...
```
[load_worktree_view_data](worktree_manager/main_window_vm.py#L179) already loops over worktrees emitting progress — add the dirty check in that same loop (runs off the UI thread via `BackgroundJob`).
[_add_row](worktree_manager/ui/per_repo_worktrees_view.py#L169) builds `dot` then `name_label`; insert the marker immediately after `name_label`.

## Constraints / invariants
- Dirty check runs inside the existing `BackgroundJob` loop — never on the UI thread.
- Clean worktrees must not shift layout beyond the marker's own (absent) slot.
- No silent exceptions — if `has_uncommitted_changes` raises, let it surface via the existing `_on_refresh_failed` path.

## Done when (gate items)
- [ ] In a repo with one worktree that has uncommitted changes and one clean, the dirty one shows an orange ● after its name; the clean one shows none.
- [ ] Hovering the ● shows tooltip "Uncommitted changes".
- [ ] Committing/stashing the changes and refreshing removes the marker.

## TDD mode: <Reviewed | Autonomous>
