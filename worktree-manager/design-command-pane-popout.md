# Command Pane Popout — Design

## Behaviour

Clicking **⤢** on a command pane opens it in a large separate window. The popout has the exact same header buttons as the normal pane. The original pane stays in the Command Center unchanged. Closing the popout window (OS ×) just dismisses it — the pane remains in the Command Center with output still streaming.

---

## 1. Normal Pane State

```
┌──────────────────────────────────────────────────┐
│ pytest -q                          ● running     │
│                            ⤢  ⟳  ■  ⎘  🔍  ✕   │
├──────────────────────────────────────────────────┤
│ collected 142 items                              │
│ tests/test_command_pane.py ......                │
│ tests/test_command_runner.py ....                │
│ ▌                                                │
└──────────────────────────────────────────────────┘
```

---

## 2. Popout Window (~900×600, same buttons)

```
┌─ pytest -q — Worktree Manager ──────────── ─ □ × ─┐
│ ┌────────────────────────────────────────────────┐ │
│ │ pytest -q                          ● running   │ │
│ │                            ⤢  ⟳  ■  ⎘  🔍  ✕  │ │
│ └────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────┐ │
│ │ collected 142 items                         ▲  │ │
│ │ tests/test_command_pane.py ..........       █  │ │
│ │ tests/test_command_runner.py ........       ░  │ │
│ │ tests/test_command_palette.py .......       ░  │ │
│ │ ▌                                           ▼  │ │
│ └────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

---

## Button Behaviour (same in both pane and popout)

| Button | Behaviour |
|---|---|
| ⤢ | In pane: opens popout. In popout: no-op (already popped out) |
| ⟳ | Restart the process |
| ■ | Stop the process |
| ⎘ | Copy output to clipboard |
| 🔍 | Toggle find bar |
| ✕ | Kill process + remove pane from Command Center + close popout if open |
| OS title-bar × | Closes the popout window only — pane stays in Command Center |

---

## Files to touch

| File | Change |
|---|---|
| `worktree_manager/ui/command_pane.py` | No button changes needed |
| `worktree_manager/ui/command_center_panel.py` | On ⤢, open popout window; wire all callbacks through |
| `worktree_manager/ui/command_popout.py` | New — `CTkToplevel` containing a `CommandPane` instance |
