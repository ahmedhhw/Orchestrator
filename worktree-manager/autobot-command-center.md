# Command Center — UI Update

## Overview
The Command Center is a global panel that lets you define named shell commands per-repo and launch them against any worktree across any repo. Running commands are displayed as tiled output panes stacked vertically in a scroll view — like tiled terminals — so you can monitor all of them at once without switching tabs. Any pane can be maximized to fill the available space. The panel is opened via a button in the bottom-left of the sidebar, making it clear it belongs to no single repo.

This document captures three UI refinements over the prior design:

1. `[+ Add Command]` is no longer in the Command Center toolbar. It now lives inside a dedicated **Commands** window/panel — a separate pane that lists saved commands and is the only place where commands are authored and edited. The Command Center toolbar is reduced to `[+ Launch]` and `[×]`.
2. The repo dropdown in both the **Launch dialog** and **Add Command dialog** remembers the last selected repo and pre-selects it on open, flagged visually with a `← last used` note.
3. A **search/filter bar** sits at the top of the running-commands area (directly below the toolbar) and filters the visible command panes by name or repo. When a search term is entered, only matching panes are shown.

## UI / Flow

### App layout — Command Center button in sidebar

`[⊞ Command Center]` sits below `[+ Add Repo]` at the bottom of the sidebar. It opens the Command Center as a full overlay over the main content area.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ┌────────────┐  ┌─────────────────────────────────────────────────┐   │
│  │  REPOS     │  │  Git Worktree Manager — my-app        ⚙  🧹    │   │
│  │────────────│  │─────────────────────────────────────────────────│   │
│  │ ● my-app   │  │  Worktrees                          [+ New]     │   │
│  │   api-svc  │  │                                                 │   │
│  │   infra    │  │  ●  main        2d ago  [OPEN]  [Focus]         │   │
│  │            │  │  ○  feat-auth   1d ago  [OPEN]  [Focus]         │   │
│  │            │  │  ○  feat-api    3d ago          [Switch]        │   │
│  │            │  │                                                 │   │
│  │────────────│  └─────────────────────────────────────────────────┘   │
│  │ + Add Repo │                                                         │
│  │⊞ Cmd Ctr  │                                                         │
│  └────────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Command Center — Empty state

No header tabs. The panel replaces the main content area entirely when open. The toolbar now holds only `[+ Launch]` and `[×]` — authoring commands has moved to the **Commands** window. A search bar sits directly below the toolbar so the user can filter running panes; in the empty state it is shown but inactive (no panes to filter).

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ┌────────────┐  ┌─────────────────────────────────────────────────┐   │
│  │  REPOS     │  │  Command Center                  [+ Launch] [×] │   │
│  │────────────│  │─────────────────────────────────────────────────│   │
│  │ ● my-app   │  │  [ 🔍 Filter running commands by name or repo…] │   │
│  │   api-svc  │  │─────────────────────────────────────────────────│   │
│  │   infra    │  │                                                 │   │
│  │            │  │         No commands running.                    │   │
│  │            │  │         Click [+ Launch] to start one.          │   │
│  │            │  │                                                 │   │
│  │            │  │         Manage saved commands in the            │   │
│  │            │  │         [Commands] window.                      │   │
│  │            │  │                                                 │   │
│  │────────────│  └─────────────────────────────────────────────────┘   │
│  │ + Add Repo │                                                         │
│  │⊞ Cmd Ctr  │                                                         │
│  └────────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Command Center — Multiple commands running (tiled view, unfiltered)

Each running command gets its own output pane. Panes are stacked vertically inside a scroll view. Each pane header shows the command identity and its controls on the right: `[⤢]` maximize, `[⟳]` restart, `[■]` stop, `[⎘]` copy. The search bar is empty here, so all panes are visible.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ┌────────────┐  ┌─────────────────────────────────────────────────┐   │
│  │  REPOS     │  │  Command Center                  [+ Launch] [×] │   │
│  │────────────│  │─────────────────────────────────────────────────│   │
│  │ ● my-app   │  │  [ 🔍 Filter running commands by name or repo…] │   │
│  │   api-svc  │  │─────────────────────────────────────────────────│   │
│  │   infra    │  │  ┌───────────────────────────────────────────┐  │   │
│  │            │  │  │ ● frontend · my-app : feat-auth  [⤢][⟳][■][⎘] │  │   │
│  │            │  │  │  > npm run dev                            │  │   │
│  │            │  │  │  vite v5.0.0  ready on :5173              │  │   │
│  │            │  │  │  watching for file changes...  █          │  │   │
│  │            │  │  └───────────────────────────────────────────┘  │   │
│  │            │  │  ┌───────────────────────────────────────────┐  │   │
│  │            │  │  │ ● backend · my-app : feat-auth   [⤢][⟳][■][⎘] │  │   │
│  │            │  │  │  > python manage.py runserver             │  │   │
│  │            │  │  │  Starting dev server on :8000             │  │   │
│  │            │  │  │  Watching for changes...  █               │  │   │
│  │            │  │  └───────────────────────────────────────────┘  │   │
│  │            │  │  ┌───────────────────────────────────────────┐  │   │
│  │            │  │  │ ○ server · api-svc : main        [⤢][⟳][■][⎘] │  │   │
│  │            │  │  │  > go run ./cmd/server                    │  │   │
│  │            │  │  │  Process exited (0)                       │  │   │
│  │            │  │  └───────────────────────────────────────────┘  │   │
│  │────────────│  └─────────────────────────────────────────────────┘   │
│  │ + Add Repo │                              ▲ scroll                   │
│  │⊞ Cmd Ctr  │                                                         │
│  └────────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

Pane header dot states:
```
●  green  — process running
○  grey   — process exited cleanly (code 0)
✕  red    — process exited with error (non-zero)
```

---

### Command Center — Filtered state

Typing into the search bar filters visible panes by case-insensitive substring match against both the command name and the repo name. Non-matching panes are hidden from the scroll view (not unmounted — re-showing them on clear is instant). A small match summary appears on the right of the search bar.

Example: user has typed `my-app` — only panes whose repo is `my-app` are visible. The `api-svc` pane is hidden.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ┌────────────┐  ┌─────────────────────────────────────────────────┐   │
│  │  REPOS     │  │  Command Center                  [+ Launch] [×] │   │
│  │────────────│  │─────────────────────────────────────────────────│   │
│  │ ● my-app   │  │  [ 🔍 my-app______________________] 2 of 3 [×]  │   │
│  │   api-svc  │  │─────────────────────────────────────────────────│   │
│  │   infra    │  │  ┌───────────────────────────────────────────┐  │   │
│  │            │  │  │ ● frontend · my-app : feat-auth  [⤢][⟳][■][⎘] │  │   │
│  │            │  │  │  > npm run dev                            │  │   │
│  │            │  │  │  vite v5.0.0  ready on :5173              │  │   │
│  │            │  │  │  watching for file changes...  █          │  │   │
│  │            │  │  └───────────────────────────────────────────┘  │   │
│  │            │  │  ┌───────────────────────────────────────────┐  │   │
│  │            │  │  │ ● backend · my-app : feat-auth   [⤢][⟳][■][⎘] │  │   │
│  │            │  │  │  > python manage.py runserver             │  │   │
│  │            │  │  │  Starting dev server on :8000             │  │   │
│  │            │  │  │  Watching for changes...  █               │  │   │
│  │            │  │  └───────────────────────────────────────────┘  │   │
│  │            │  │                                                 │   │
│  │            │  │  (1 pane hidden by filter — clear to show all)  │   │
│  │            │  │                                                 │   │
│  │────────────│  └─────────────────────────────────────────────────┘   │
│  │ + Add Repo │                                                         │
│  │⊞ Cmd Ctr  │                                                         │
│  └────────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

Search bar behavior:
- Empty string → all panes visible (no filter applied).
- Non-empty string → filter matches against `cmd_name` and `repo_name` (case-insensitive substring).
- `[×]` on the right clears the filter and restores all panes.
- `Esc` while the search input has focus also clears it.
- The filter affects display only; processes continue running and output continues streaming to hidden panes.
- When a filter is active and zero panes match, a hint line is shown: `No running commands match "<term>". [Clear]`.

Zero-match filtered state:

```
┌─────────────────────────────────────────────────┐
│  Command Center                  [+ Launch] [×] │
│─────────────────────────────────────────────────│
│  [ 🔍 nope_______________________ ] 0 of 3 [×]  │
│─────────────────────────────────────────────────│
│                                                 │
│       No running commands match "nope".         │
│                  [Clear filter]                 │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

### Command Center — Maximized pane

Clicking `[⤢]` on a pane expands it to fill the entire Command Center content area below the search bar. All other panes are hidden. `[⤡]` in the same position restores the tiled view. The search bar remains visible (and editable) but does not affect a maximized pane — exiting maximize returns to the previous filter state.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ┌────────────┐  ┌─────────────────────────────────────────────────┐   │
│  │  REPOS     │  │  Command Center                  [+ Launch] [×] │   │
│  │────────────│  │─────────────────────────────────────────────────│   │
│  │ ● my-app   │  │  [ 🔍 Filter running commands by name or repo…] │   │
│  │   api-svc  │  │─────────────────────────────────────────────────│   │
│  │   infra    │  │  ┌───────────────────────────────────────────┐  │   │
│  │            │  │  │ ● frontend · my-app : feat-auth  [⤡][⟳][■][⎘] │  │   │
│  │            │  │  │  > npm run dev                            │  │   │
│  │            │  │  │  vite v5.0.0  ready on :5173              │  │   │
│  │            │  │  │  [lots of output...]                      │  │   │
│  │            │  │  │                                           │  │   │
│  │            │  │  │                                           │  │   │
│  │            │  │  │  watching for file changes...  █          │  │   │
│  │            │  │  └───────────────────────────────────────────┘  │   │
│  │────────────│  └─────────────────────────────────────────────────┘   │
│  │ + Add Repo │                                                         │
│  │⊞ Cmd Ctr  │                                                         │
│  └────────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Commands window — saved-command library

A separate window/panel that lists all saved commands across all repos. This is where `[+ Add Command]` now lives — prominently in the window's own toolbar. Opened via a `[Commands]` menu item, from a button in the Launch dialog, or via `Cmd+Shift+K`. Each row shows repo, name, and command string with inline `[Edit]` / `[Delete]` controls. The window can be left open alongside the Command Center.

```
┌─────────────────────────────────────────────────────────────┐
│  Commands                          [+ Add Command]  [×]     │
│─────────────────────────────────────────────────────────────│
│  [ 🔍 Filter by name, repo, or command…                  ] │
│─────────────────────────────────────────────────────────────│
│  Repo       Name       Command                  Actions    │
│─────────────────────────────────────────────────────────────│
│  my-app     frontend   npm run dev          [Edit] [Del]   │
│  my-app     backend    python manage.py …   [Edit] [Del]   │
│  my-app     test       npm test             [Edit] [Del]   │
│  api-svc    server     go run ./cmd/server  [Edit] [Del]   │
│  api-svc    lint       golangci-lint run    [Edit] [Del]   │
│  infra      plan       terraform plan       [Edit] [Del]   │
│─────────────────────────────────────────────────────────────│
│  6 saved commands across 3 repos                            │
└─────────────────────────────────────────────────────────────┘
```

Empty state for the Commands window:

```
┌─────────────────────────────────────────────────────────────┐
│  Commands                          [+ Add Command]  [×]     │
│─────────────────────────────────────────────────────────────│
│                                                             │
│           No saved commands yet.                            │
│           Click [+ Add Command] to create one.              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Behavior notes:
- `[+ Add Command]` opens the Add Command dialog (see below).
- `[Edit]` opens the Add Command dialog pre-filled with the row's values; Save updates in place.
- `[Delete]` prompts for confirmation, then removes via `vm.delete_command(repo_path, name)`.
- The filter row is local to the Commands window and does not affect Command Center filtering.

---

### Command palette (Cmd+K) — launch a saved command quickly

Triggered by `Cmd+K` anywhere in the app. A floating dialog appears centered over the content area. Typing filters saved commands across all repos by name. Arrow keys move the selection; `Enter` launches the highlighted result against the last-used worktree for that repo (pre-filled in the Worktree field, but editable). `Esc` dismisses.

```
        ┌─────────────────────────────────────────────┐
        │ 🔍 front__________________________           │
        │─────────────────────────────────────────────│
        │ ▶ frontend · my-app    [feat-auth      ▾]  │  ← selected
        │   frontend · api-svc   [main           ▾]  │
        │─────────────────────────────────────────────│
        │  ↑↓ navigate   Enter launch   Esc dismiss   │
        └─────────────────────────────────────────────┘
```

Each result row has an inline Worktree dropdown so you can change the target without leaving the palette. Launching closes the palette and opens the Command Center panel if not already open.

---

### Per-pane output search (Ctrl+F)

`Ctrl+F` (or clicking a `[🔍]` icon in the pane header) reveals a find bar inside that pane. Matches are highlighted in the output. `↑` / `↓` or `Enter` / `Shift+Enter` step through matches. `Esc` dismisses. This is distinct from the top-level Command Center filter — that one filters which panes are visible, while this one searches text within a single pane.

```
  ┌─────────────────────────────────────────────────────┐
  │ ● frontend · my-app : feat-auth  [⤢][⟳][■][⎘][🔍] │
  │─────────────────────────────────────────────────────│
  │  [ 🔍 error____________ ]  match 2 of 4  [↑] [↓] [×]│
  │  > npm run dev                                      │
  │  vite v5.0.0  ready on :5173                        │
  │  Error: cannot find module './foo'    ← highlighted  │
  │  watching for file changes...                       │
  │  Error: failed to resolve import     ← highlighted  │
  └─────────────────────────────────────────────────────┘
```

---

### Add Command dialog

Opened from `[+ Add Command]` inside the **Commands** window (no longer reachable from the Command Center toolbar). The Repo dropdown pre-selects the last repo the user picked in either dialog — a `← last used` annotation makes the pre-selection visible so the user knows the choice was carried over.

```
┌────────────────────────────────────────────────────┐
│  Add Saved Command                                 │
│────────────────────────────────────────────────────│
│  Repo:     [ my-app                ▾ ]  ← last used│
│  Name:     [ frontend                          ]   │
│  Command:                                          │
│  ┌──────────────────────────────────────────────┐  │
│  │ npm run dev                                  │  │
│  └──────────────────────────────────────────────┘  │
│                              [Cancel]  [Save]      │
└────────────────────────────────────────────────────┘
```

First-use state (no last-used repo yet — falls back to the first repo alphabetically, no annotation):

```
┌────────────────────────────────────────────────────┐
│  Add Saved Command                                 │
│────────────────────────────────────────────────────│
│  Repo:     [ api-svc               ▾ ]             │
│  Name:     [                                   ]   │
│  Command:                                          │
│  ┌──────────────────────────────────────────────┐  │
│  │                                              │  │
│  └──────────────────────────────────────────────┘  │
│                              [Cancel]  [Save]      │
└────────────────────────────────────────────────────┘
```

Persistence note: the last-used repo is saved on Save (not on dropdown change) and is shared with the Launch dialog so the two stay in sync. It persists across app restarts via `config.json` (`last_used_repo` key alongside the existing `repos` map).

---

### Launch dialog (via [+ Launch])

Full cross-repo picker. Selecting a repo refreshes the Command and Worktree dropdowns to show only that repo's data. The Repo dropdown pre-selects the last-used repo on open, with the same `← last used` annotation as the Add Command dialog. The Command and Worktree dropdowns default to the first available value for that repo (the user can still change them).

```
┌──────────────────────────────────────────────────┐
│  Launch Command                                  │
│──────────────────────────────────────────────────│
│  Repo:     [ my-app          ▾ ]  ← last used   │
│  Command:  [ frontend        ▾ ]                 │
│  Worktree: [ feat-auth       ▾ ]                 │
│                          [Cancel]  [Launch]      │
└──────────────────────────────────────────────────┘
```

First-use state (no last-used repo yet):

```
┌──────────────────────────────────────────────────┐
│  Launch Command                                  │
│──────────────────────────────────────────────────│
│  Repo:     [ api-svc         ▾ ]                 │
│  Command:  [ server          ▾ ]                 │
│  Worktree: [ main            ▾ ]                 │
│                          [Cancel]  [Launch]      │
└──────────────────────────────────────────────────┘
```

Behavior notes:
- On open, the Repo dropdown is set to `vm.last_used_repo()`. If that value is null or no longer present in `all_repos()`, fall back to the first repo alphabetically and show no annotation.
- The `← last used` annotation is rendered to the right of the dropdown; it disappears if the user changes the selection (a different repo is no longer "last used" from the user's perspective in this dialog).
- On Launch, the chosen repo is persisted as the new last-used value — so the next time either dialog opens, it will show the most recent choice.
