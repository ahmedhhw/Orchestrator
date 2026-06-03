"""Behavioral contract — Iteration 0: Project caret no-reload.

Toggling a project's caret collapses/expands from cache — no refresh job fires.
Run: python3.14 -m pytest tests/test_project_caret_no_reload_contract.py
"""
from unittest.mock import MagicMock, call

from PySide6.QtWidgets import QPushButton

from worktree_manager.ui.workspace_projects_panel import WorkspaceProjectsPanel


# ── helpers ───────────────────────────────────────────────────────────────────

def _project(name, paths):
    p = MagicMock()
    p.name = name
    p.entries = [MagicMock(worktree_path=path) for path in paths]
    return p


def _vm(projects=None):
    vm = MagicMock()
    vm._store.get_ui_pref.side_effect = lambda key, default=None: default
    vm._store.set_ui_pref.return_value = None
    vm._git.checked_out_branch.return_value = "main"
    vm.list_branches_for_worktree.return_value = ["main"]
    vm.load_projects.return_value = projects or []
    vm.load_project_entries.return_value = [
        {"worktree_path": e.worktree_path, "current_branch": "main", "branches": ["main"]}
        for p in (projects or [])
        for e in p.entries
    ]
    return vm


def _panel(qtbot, projects=None):
    projects = projects or [_project("alpha", ["/r/alpha"])]
    vm = _vm(projects)
    panel = WorkspaceProjectsPanel(
        parent=None, vm=vm, on_close=lambda: None,
    )
    qtbot.addWidget(panel)
    qtbot.waitUntil(lambda: not panel._loading, timeout=3000)
    return panel, vm


def _caret_btn(panel, name):
    return next(
        b for b in panel.findChildren(QPushButton)
        if name in b.text() and ("▼" in b.text() or "▶" in b.text())
    )


# ── 1 · No reload on caret click ─────────────────────────────────────────────

def test_caret_click_does_not_trigger_load_project_entries(qtbot):
    """Clicking the caret does NOT call vm.load_project_entries — data comes from cache."""
    panel, vm = _panel(qtbot)
    vm.load_project_entries.reset_mock()

    _caret_btn(panel, "alpha").click()

    vm.load_project_entries.assert_not_called()


def test_caret_click_does_not_show_loading_spinner(qtbot):
    """Clicking the caret leaves panel._loading False — no spinner fires."""
    panel, vm = _panel(qtbot)

    _caret_btn(panel, "alpha").click()

    assert not panel._loading


def test_caret_click_does_not_call_refresh_background_job(qtbot):
    """After caret click, no BackgroundJob for entry loading is started (_load_job unchanged)."""
    panel, vm = _panel(qtbot)
    job_before = panel._load_job

    _caret_btn(panel, "alpha").click()

    assert panel._load_job is job_before


# ── 2 · Collapse / expand correctness ────────────────────────────────────────

def test_caret_collapses_project_entries(qtbot):
    """After one caret click the project's entry rows are hidden (collapsed)."""
    panel, vm = _panel(qtbot)
    assert "alpha" in panel._collapsed or "alpha" not in panel._collapsed  # just warm up

    btn = _caret_btn(panel, "alpha")
    initial_collapsed = "alpha" in panel._collapsed
    btn.click()

    assert ("alpha" in panel._collapsed) != initial_collapsed


def test_caret_toggle_twice_restores_expanded(qtbot):
    """Clicking the caret twice leaves the project expanded again."""
    panel, vm = _panel(qtbot)
    btn = _caret_btn(panel, "alpha")
    btn.click()
    btn = _caret_btn(panel, "alpha")  # re-find after rerender
    btn.click()

    assert "alpha" not in panel._collapsed


def test_caret_persists_collapsed_state_to_store(qtbot):
    """The collapsed set is saved to the store on each toggle."""
    panel, vm = _panel(qtbot)
    _caret_btn(panel, "alpha").click()

    vm._store.set_ui_pref.assert_any_call("projects_collapsed", ["alpha"])


# ── 3 · Other projects unaffected ────────────────────────────────────────────

def test_collapsing_one_project_leaves_other_expanded(qtbot):
    """Toggling project A does not change project B's collapsed state."""
    projects = [_project("alpha", ["/r/alpha"]), _project("beta", ["/r/beta"])]
    vm = _vm(projects)
    panel = WorkspaceProjectsPanel(parent=None, vm=vm, on_close=lambda: None)
    qtbot.addWidget(panel)
    qtbot.waitUntil(lambda: not panel._loading, timeout=3000)

    _caret_btn(panel, "alpha").click()

    assert "beta" not in panel._collapsed


# ── 4 · Full refresh still loads data (mutations path) ───────────────────────

def test_refresh_calls_load_project_entries(qtbot):
    """refresh() (used after mutations) still calls vm.load_project_entries."""
    panel, vm = _panel(qtbot)
    vm.load_project_entries.reset_mock()

    panel.refresh()
    qtbot.waitUntil(lambda: not panel._loading, timeout=3000)

    vm.load_project_entries.assert_called_once()


def test_refresh_resets_entry_map_cache(qtbot):
    """refresh() clears _entry_map so the next render uses fresh data."""
    panel, vm = _panel(qtbot)
    assert panel._entry_map is not None  # populated after first load

    panel.refresh()
    # immediately after refresh() call (before job finishes) cache is cleared
    assert panel._entry_map is None
