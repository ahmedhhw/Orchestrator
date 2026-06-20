# Context: Iteration 3 — Persist full PR detail to cache

## Goal
The on-disk cache stores the **full** PR detail — `run_id` on checks, plus reviews and comments —
under a versioned envelope, so after a cold start the View pane is complete and **Re-try CIs** works
immediately, without waiting for the first network fetch.

## Tests to write
- Saving the cache writes a versioned envelope with a top-level version and a prs list: proves new format.
- A saved check round-trips its run_id: proves the latent re-run-from-cache bug is fixed.
- Saved PR rows round-trip their reviews and comments: proves detail persists.
- Loading a new-format cache reconstructs PRs with checks (incl. run_id), reviews and comments: proves symmetric load.
- Loading an old list-shaped (versionless) cache starts empty without raising: proves backward tolerance.
- Loading a corrupt cache starts empty and logs a warning: proves no crash, no silent pass.

## Files to touch
- [github_vm.py](worktree_manager/github_vm.py) — `_save_pr_cache` writes `{version, prs:[…]}` with run_id/reviews/comments; `_load_pr_cache` reads it and tolerates old/corrupt files.

## Design / pseudocode

#### `worktree_manager/github_vm.py`
```
CACHE_VERSION = 1

_save_pr_cache:
    rows = [ {
        number, title, html_url, head_branch, base_branch, head_sha,
        state, draft, mergeable, mergeable_state, owner, repo,
        checks:   [ {name, status, conclusion, check_suite_id, run_id} ],   # +run_id
        reviews:  [ {author, state} ],                                       # NEW
        comments: [ {id, author, body, created_at} ],                        # NEW
    } for p in self.prs ]
    write json { "version": CACHE_VERSION, "prs": rows }

_load_pr_cache:
    if not path.exists(): return []
    try:
        raw = json.loads(path.read_text())
        rows = raw["prs"] if isinstance(raw, dict) and "version" in raw else []   # old list → empty
        return [ PullRequest(... checks=[CICheck(**c) for c in row["checks"]],
                             reviews=[Review(**r) for r in row.get("reviews", [])],
                             comments=[PRComment(**k) for k in row.get("comments", [])],
                             head_sha=row.get("head_sha","")) for row in rows ]
    except Exception:
        log.warning("Failed to load PR cache; starting empty", exc_info=True); return []
```

## Diagrams
*(none — straight serialization change)*

## Relevant existing code

`_save_pr_cache` today — note it omits `run_id`, `reviews`, `comments`, `head_sha` ([github_vm.py:257](worktree_manager/github_vm.py#L257)).
`_load_pr_cache` today — reads a flat list ([github_vm.py:289](worktree_manager/github_vm.py#L289)).

Model fields available to persist ([github_models.py](worktree_manager/github_models.py)):
```python
@dataclass class CICheck: name; status; conclusion; check_suite_id=None; run_id=None
@dataclass class Review:  author; state
@dataclass class PRComment: id; author; body; created_at; seen=False
@dataclass class PullRequest: number,title,body,html_url,head_branch,base_branch,
    state,draft,mergeable, checks=[], reviews=[], comments=[], head_sha="", owner,repo, mergeable_state
```

Existing cache tests: [test_github_pr_cache.py](tests/test_github_pr_cache.py).

Real current on-disk file (1 PR) is `~/.config/worktree-manager/github_pr_cache.json` — a flat list,
checks missing `run_id` (live `run_id` for that check is `26702825172`).

## Constraints / invariants
- **Stored-data guardrail:** before the first write of the new format, show a real before→after diff of `github_pr_cache.json` and get acknowledgement.
- Loader must never raise on an old/corrupt file — start empty (a fresh `total_fetch` repopulates).
- `PRComment` has a `seen` field with a default — don't fail if absent in old data.
- The `github_pr_state.json` format is unchanged.
- No silent exceptions (the load `except` logs a warning — that is surfacing, not swallowing).

## Done when (gate items)
- [ ] After a normal session, `github_pr_cache.json` is the `{ "version": 1, "prs": [...] }` shape with `run_id`, `reviews`, `comments` present.
- [ ] Cold start (kill app, relaunch): opening a PR shows its reviews/comments immediately from cache (before any fresh fetch).
- [ ] Cold start: **Re-try failed CIs** is available immediately on a cached PR with a failed Actions check (run_id survived).
- [ ] An old (pre-change) cache file does not crash the app — PR list just starts empty and repopulates on fetch.
- [ ] Regression: list/startup, instant View, and non-freezing actions all still work (Iterations 0–2).

## TDD mode: <set when built>
