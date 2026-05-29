from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QListWidget, QLineEdit

from worktree_manager.ui.diff_point_selector import DiffPointSelector
from worktree_manager.diff_models import HistoryPoint


def _make_points():
    return [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="working_tree_staged",   label="Working tree (staged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc1234", message="Merge PR"),
        HistoryPoint(kind="branch", label="feature/login", short_sha="def5678", message="Auth"),
        HistoryPoint(kind="commit", label="ghi9012", short_sha="ghi9012", message="Fix tests"),
    ]


def _make_selector(qtbot, points=None):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    if points is not None:
        sel.set_repo("/repo", points)
    return sel


# ── structure ─────────────────────────────────────────────────────────────────

def test_selector_has_from_list(qtbot):
    sel = _make_selector(qtbot, _make_points())
    assert sel._from_list is not None
    assert isinstance(sel._from_list, QListWidget)


def test_selector_has_to_list(qtbot):
    sel = _make_selector(qtbot, _make_points())
    assert sel._to_list is not None
    assert isinstance(sel._to_list, QListWidget)


def test_selector_has_from_filter(qtbot):
    sel = _make_selector(qtbot, _make_points())
    assert isinstance(sel._from_filter, QLineEdit)


def test_selector_has_to_filter(qtbot):
    sel = _make_selector(qtbot, _make_points())
    assert isinstance(sel._to_filter, QLineEdit)


def test_selector_has_compare_button(qtbot):
    sel = _make_selector(qtbot, _make_points())
    btns = sel.findChildren(QPushButton)
    assert any("Compare" in b.text() for b in btns)


# ── population ────────────────────────────────────────────────────────────────

def test_set_repo_populates_from_list(qtbot):
    sel = _make_selector(qtbot, _make_points())
    texts = [sel._from_list.item(i).text() for i in range(sel._from_list.count())]
    assert any("Working tree (unstaged)" in t for t in texts)
    assert any("main" in t for t in texts)


def test_set_repo_populates_to_list(qtbot):
    sel = _make_selector(qtbot, _make_points())
    texts = [sel._to_list.item(i).text() for i in range(sel._to_list.count())]
    assert any("Working tree (unstaged)" in t for t in texts)
    assert any("feature/login" in t for t in texts)


def test_list_items_show_sha_for_branch_points(qtbot):
    sel = _make_selector(qtbot, _make_points())
    texts = [sel._from_list.item(i).text() for i in range(sel._from_list.count())]
    assert any("abc1234" in t for t in texts)


def test_list_items_show_message_for_branch_points(qtbot):
    sel = _make_selector(qtbot, _make_points())
    texts = [sel._from_list.item(i).text() for i in range(sel._from_list.count())]
    assert any("Merge PR" in t for t in texts)


# ── filter ────────────────────────────────────────────────────────────────────

def test_from_filter_narrows_visible_items(qtbot):
    sel = _make_selector(qtbot, _make_points())
    sel._from_filter.setText("main")
    visible_count = sum(
        1 for i in range(sel._from_list.count())
        if not sel._from_list.item(i).isHidden()
    )
    assert visible_count < sel._from_list.count()


def test_from_filter_shows_matching_items(qtbot):
    sel = _make_selector(qtbot, _make_points())
    sel._from_filter.setText("main")
    visible_texts = [
        sel._from_list.item(i).text()
        for i in range(sel._from_list.count())
        if not sel._from_list.item(i).isHidden()
    ]
    assert any("main" in t for t in visible_texts)


def test_to_filter_narrows_visible_items(qtbot):
    sel = _make_selector(qtbot, _make_points())
    sel._to_filter.setText("feature")
    visible_count = sum(
        1 for i in range(sel._to_list.count())
        if not sel._to_list.item(i).isHidden()
    )
    assert visible_count < sel._to_list.count()


def test_clearing_filter_restores_all_items(qtbot):
    sel = _make_selector(qtbot, _make_points())
    total = sel._from_list.count()
    sel._from_filter.setText("main")
    sel._from_filter.setText("")
    visible_count = sum(
        1 for i in range(sel._from_list.count())
        if not sel._from_list.item(i).isHidden()
    )
    assert visible_count == total


# ── compare callback ──────────────────────────────────────────────────────────

def test_on_compare_callback_fires_with_selected_refs(qtbot):
    sel = _make_selector(qtbot, _make_points())
    result = []
    sel.on_compare(lambda base, target: result.append((base, target)))
    sel._from_list.setCurrentRow(2)  # main
    sel._to_list.setCurrentRow(0)   # working_tree_unstaged
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert len(result) == 1
    base, target = result[0]
    assert base == "main"
    assert target == "working_tree_unstaged"


def test_compare_button_does_not_fire_when_no_from_selected(qtbot):
    sel = _make_selector(qtbot, _make_points())
    result = []
    sel.on_compare(lambda base, target: result.append((base, target)))
    sel._to_list.setCurrentRow(0)
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert result == []


def test_compare_button_does_not_fire_when_no_to_selected(qtbot):
    sel = _make_selector(qtbot, _make_points())
    result = []
    sel.on_compare(lambda base, target: result.append((base, target)))
    sel._from_list.setCurrentRow(2)
    btn = next(b for b in sel.findChildren(QPushButton) if "Compare" in b.text())
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert result == []
