from worktree_manager.ui.diff_point_selector import DiffPointSelector
from worktree_manager.diff_models import HistoryPoint
from PySide6.QtWidgets import QLabel


def _make_points():
    return [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc", message="init"),
    ]


def _make_selector(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points())
    return sel


def test_newer_point_label_shown(qtbot):
    sel = _make_selector(qtbot)
    labels = [w.text() for w in sel.findChildren(QLabel)]
    assert any("NEWER POINT" in t for t in labels)


def test_older_point_label_shown(qtbot):
    sel = _make_selector(qtbot)
    labels = [w.text() for w in sel.findChildren(QLabel)]
    assert any("OLDER POINT" in t for t in labels)


def test_from_label_not_shown(qtbot):
    sel = _make_selector(qtbot)
    labels = [w.text() for w in sel.findChildren(QLabel)]
    assert not any("FROM" in t and "base" in t for t in labels)


def test_to_label_not_shown(qtbot):
    sel = _make_selector(qtbot)
    labels = [w.text() for w in sel.findChildren(QLabel)]
    assert not any("TO" in t and "target" in t for t in labels)


def test_newer_point_list_is_above_older_point_list(qtbot):
    sel = _make_selector(qtbot)
    sel.show()
    newer_y = sel._newer_list.mapTo(sel, sel._newer_list.rect().topLeft()).y()
    older_y = sel._older_list.mapTo(sel, sel._older_list.rect().topLeft()).y()
    assert newer_y < older_y
