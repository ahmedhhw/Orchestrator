import pytest
from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Qt
from worktree_manager.ui.diff_point_selector import DiffPointSelector
from worktree_manager.diff_models import HistoryPoint


def _make_points():
    return [
        HistoryPoint(kind="working_tree_unstaged", label="Working tree (unstaged)"),
        HistoryPoint(kind="working_tree_staged", label="Working tree (staged)"),
        HistoryPoint(kind="branch", label="main", short_sha="abc", message="init"),
        HistoryPoint(kind="branch", label="feature/foo", short_sha="def", message="foo"),
    ]


def _all_texts(lst: QListWidget) -> list[str]:
    return [lst.item(i).text() for i in range(lst.count())]


def test_suggested_section_header_shown_in_older_list(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points(), suggested_older=["main"])
    texts = _all_texts(sel._older_list)
    assert any("Suggested" in t for t in texts)


def test_suggested_section_header_shown_in_newer_list(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points(), suggested_newer=["working_tree_unstaged"])
    texts = _all_texts(sel._newer_list)
    assert any("Suggested" in t for t in texts)


def test_suggested_ref_appears_at_top_of_older_list(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points(), suggested_older=["main"])
    texts = _all_texts(sel._older_list)
    # "★ Suggested" header first, then "main" among the next few items
    star_idx = next(i for i, t in enumerate(texts) if "Suggested" in t)
    main_idx = next(i for i, t in enumerate(texts) if "main" in t and i > star_idx)
    assert main_idx == star_idx + 1


def test_separator_appears_between_suggested_and_rest(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points(), suggested_older=["main"])
    texts = _all_texts(sel._older_list)
    star_idx = next(i for i, t in enumerate(texts) if "Suggested" in t)
    # there should be a separator item (empty or dashes) after the suggested refs
    sep_idx = star_idx + 2  # header + 1 suggested ref + separator
    assert texts[sep_idx] == "" or "─" in texts[sep_idx] or texts[sep_idx].strip() == ""


def test_suggested_items_have_user_role_ref(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points(), suggested_older=["main"])
    # find the "main" item in the suggested section and verify its UserRole data
    for i in range(sel._older_list.count()):
        item = sel._older_list.item(i)
        if "main" in item.text() and item.data(Qt.UserRole) == "main":
            return
    pytest.fail("No item with UserRole=='main' found in older list")


def test_no_suggested_section_when_no_suggestions(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points())
    texts = _all_texts(sel._older_list)
    assert not any("Suggested" in t for t in texts)


def test_all_points_still_present_after_section(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points(), suggested_older=["main"])
    texts = _all_texts(sel._older_list)
    assert any("Working tree (unstaged)" in t for t in texts)
    assert any("feature/foo" in t for t in texts)


def test_suggested_header_item_is_not_selectable(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points(), suggested_older=["main"])
    for i in range(sel._older_list.count()):
        item = sel._older_list.item(i)
        if "Suggested" in item.text():
            assert not (item.flags() & Qt.ItemIsSelectable)
            return
    pytest.fail("No Suggested header item found")


def test_separator_item_is_not_selectable(qtbot):
    sel = DiffPointSelector()
    qtbot.addWidget(sel)
    sel.set_repo("/repo", _make_points(), suggested_older=["main"])
    texts = _all_texts(sel._older_list)
    star_idx = next(i for i, t in enumerate(texts) if "Suggested" in t)
    sep_idx = star_idx + 2
    item = sel._older_list.item(sep_idx)
    assert not (item.flags() & Qt.ItemIsSelectable)
