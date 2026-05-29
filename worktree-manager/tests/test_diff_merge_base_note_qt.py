from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt

from worktree_manager.ui.diff_point_selector import DiffPointSelector
from worktree_manager.diff_models import HistoryPoint


def _make_points():
    return [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc1234", message="Main commit"),
        HistoryPoint(kind="branch", label="feature/login", short_sha="def5678", message="Auth flow"),
    ]


def _make_selector(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    return sel


def _select_from_by_ref(sel, ref):
    for i in range(sel._from_list.count()):
        item = sel._from_list.item(i)
        if item.data(Qt.UserRole) == ref:
            sel._from_list.setCurrentItem(item)
            return


def test_merge_base_note_hidden_by_default(qtbot):
    sel = _make_selector(qtbot)
    sel.set_repo("/repo", _make_points(), git_service=None)
    assert sel._merge_base_note.isHidden()


def test_merge_base_note_shown_when_from_is_branch(qtbot):
    svc = MagicMock()
    svc.resolve_merge_base.return_value = "abc0001"
    sel = _make_selector(qtbot)
    sel.set_repo("/repo", _make_points(), git_service=svc)
    _select_from_by_ref(sel, "feature/login")
    assert not sel._merge_base_note.isHidden()
    assert "abc0001" in sel._merge_base_note.text()
    assert "feature/login" in sel._merge_base_note.text()


def test_merge_base_note_hidden_when_from_is_working_tree(qtbot):
    svc = MagicMock()
    sel = _make_selector(qtbot)
    sel.set_repo("/repo", _make_points(), git_service=svc)
    _select_from_by_ref(sel, "working_tree_unstaged")
    assert sel._merge_base_note.isHidden()


def test_merge_base_note_hidden_when_from_is_commit(qtbot):
    svc = MagicMock()
    svc.resolve_merge_base.return_value = "abc1234"
    points = _make_points() + [
        HistoryPoint(kind="commit", label="abc1234", short_sha="abc1234", message="Fix tests"),
    ]
    sel = _make_selector(qtbot)
    sel.set_repo("/repo", points, git_service=svc)
    _select_from_by_ref(sel, "abc1234")
    assert sel._merge_base_note.isHidden()


def test_merge_base_error_silently_hides_note(qtbot):
    import subprocess
    svc = MagicMock()
    svc.resolve_merge_base.side_effect = subprocess.CalledProcessError(1, "git")
    sel = _make_selector(qtbot)
    sel.set_repo("/repo", _make_points(), git_service=svc)
    _select_from_by_ref(sel, "feature/login")
    assert sel._merge_base_note.isHidden()
