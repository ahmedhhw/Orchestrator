import time
from unittest.mock import MagicMock

from worktree_manager.main_window_vm import MainWindowViewModel
from worktree_manager.models import WorktreeModel
from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView


def _make_vm():
    now = int(time.time())
    vm = MagicMock(spec=MainWindowViewModel)
    vm.load_worktree_view_data.return_value = {
        "worktrees": [
            WorktreeModel("/repos/proj", "main", True, now, False, False),
            WorktreeModel("/repos/proj-wt/feat", "feature/x", False, now - 3600, False, False),
        ],
        "branch_status": [("main", True), ("feature/x", True)],
    }
    return vm


def _make_view(qtbot, on_diff_from_working_tree=None, on_diff_compare_branches=None):
    view = PerRepoWorktreesView(
        vm=_make_vm(),
        repo_name="proj",
        on_cleanup=lambda: None,
        on_new=lambda: None,
        on_diff_from_working_tree=on_diff_from_working_tree,
        on_diff_compare_branches=on_diff_compare_branches,
    )
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: not view._loading, timeout=3000)
    return view


def test_context_menu_has_diff_from_working_tree_action(qtbot):
    view = _make_view(qtbot)
    menu = view._build_context_menu("/repos/proj-wt/feat")
    texts = [a.text() for a in menu.actions()]
    assert any("Diff from working tree" in t for t in texts)


def test_context_menu_has_compare_branches_action(qtbot):
    view = _make_view(qtbot)
    menu = view._build_context_menu("/repos/proj-wt/feat")
    texts = [a.text() for a in menu.actions()]
    assert any("Compare branches" in t for t in texts)


def test_diff_from_working_tree_fires_callback_with_repo_path(qtbot):
    called = []
    view = _make_view(qtbot, on_diff_from_working_tree=lambda path: called.append(path))
    view._trigger_diff_from_working_tree("/repos/proj-wt/feat")
    assert called == ["/repos/proj-wt/feat"]


def test_compare_branches_fires_callback_with_repo_path(qtbot):
    called = []
    view = _make_view(qtbot, on_diff_compare_branches=lambda path: called.append(path))
    view._trigger_diff_compare_branches("/repos/proj-wt/feat")
    assert called == ["/repos/proj-wt/feat"]


def test_diff_callbacks_not_required(qtbot):
    view = _make_view(qtbot)
    view._trigger_diff_from_working_tree("/repos/proj-wt/feat")
    view._trigger_diff_compare_branches("/repos/proj-wt/feat")
