import sys
sys.path.insert(0, "/Users/ahmedhhw/repos/dev-tools/worktree-manager")

import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from worktree_manager.ui.diff_point_selector import DiffPointSelector
from worktree_manager.diff_models import HistoryPoint
from PySide6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)


def _make_points():
    return [
        HistoryPoint(kind="branch", label="main", short_sha="aaa111", message="tip msg"),
        HistoryPoint(kind="branch", label="feature/foo", short_sha="bbb222", message="feat msg"),
        HistoryPoint(kind="commit", label="ccc333", short_sha="ccc333", message="old commit"),
    ]


def _make_git(merge_bases):
    git = MagicMock()
    git.resolve_merge_base.side_effect = lambda repo, branch, onto: merge_bases[branch]
    return git


def _make_store(mode="merge_base"):
    store = MagicMock()
    store.get_branch_diff_mode.return_value = mode
    return store


def test_branch_entries_show_merge_base_label_when_mode_is_merge_base():
    sel = DiffPointSelector()
    git = _make_git({"main": "aaa000", "feature/foo": "bbb000"})
    store = _make_store("merge_base")
    sel.set_repo("/repo", _make_points(), git_service=git, config_store=store)

    labels = [sel._older_list.item(i).text() for i in range(sel._older_list.count())]
    assert any("main (merge base)" in l for l in labels)
    assert any("feature/foo (merge base)" in l for l in labels)


def test_branch_entries_userrole_is_resolved_sha_when_mode_is_merge_base():
    sel = DiffPointSelector()
    git = _make_git({"main": "aaa000", "feature/foo": "bbb000"})
    store = _make_store("merge_base")
    sel.set_repo("/repo", _make_points(), git_service=git, config_store=store)

    refs = [sel._older_list.item(i).data(Qt.UserRole) for i in range(sel._older_list.count())]
    assert "aaa000" in refs
    assert "bbb000" in refs
    # original branch labels NOT used as refs
    assert "main" not in refs
    assert "feature/foo" not in refs


def test_commit_entries_unchanged_in_merge_base_mode():
    sel = DiffPointSelector()
    git = _make_git({"main": "aaa000", "feature/foo": "bbb000"})
    store = _make_store("merge_base")
    sel.set_repo("/repo", _make_points(), git_service=git, config_store=store)

    labels = [sel._older_list.item(i).text() for i in range(sel._older_list.count())]
    assert any("ccc333" in l for l in labels)


def test_branch_entries_show_raw_label_when_mode_is_branch_tip():
    sel = DiffPointSelector()
    git = MagicMock()
    store = _make_store("branch_tip")
    sel.set_repo("/repo", _make_points(), git_service=git, config_store=store)

    labels = [sel._older_list.item(i).text() for i in range(sel._older_list.count())]
    assert any("main" in l and "(merge base)" not in l for l in labels)
    git.resolve_merge_base.assert_not_called()


def test_merge_base_note_hidden_in_merge_base_mode_on_older_change():
    sel = DiffPointSelector()
    git = _make_git({"main": "aaa000", "feature/foo": "bbb000"})
    store = _make_store("merge_base")
    sel.set_repo("/repo", _make_points(), git_service=git, config_store=store)

    # select the first branch item
    for i in range(sel._older_list.count()):
        item = sel._older_list.item(i)
        if item and "main" in (item.text() or ""):
            sel._older_list.setCurrentItem(item)
            break

    assert sel._merge_base_note.isHidden()


def test_merge_base_note_shown_in_branch_tip_mode_on_older_change():
    sel = DiffPointSelector()
    git = MagicMock()
    git.resolve_merge_base.return_value = "aaa000"
    store = _make_store("branch_tip")
    sel.set_repo("/repo", _make_points(), git_service=git, config_store=store)

    main_item = None
    for i in range(sel._older_list.count()):
        item = sel._older_list.item(i)
        if item and item.data(Qt.UserRole) == "main":
            main_item = item
            break

    assert main_item is not None
    sel._on_older_changed(main_item, None)
    assert not sel._merge_base_note.isHidden()


def test_suggested_branch_entries_use_merge_base_sha_as_userrole():
    sel = DiffPointSelector()
    git = _make_git({"main": "aaa000", "feature/foo": "bbb000"})
    store = _make_store("merge_base")
    sel.set_repo(
        "/repo", _make_points(), git_service=git, config_store=store,
        suggested_older=["main", "feature/foo"],
    )

    # Collect UserRole values from the suggested section (before the separator)
    refs = []
    for i in range(sel._older_list.count()):
        item = sel._older_list.item(i)
        text = item.text() if item else ""
        if text.startswith("★") or text.startswith("─"):
            continue
        refs.append(item.data(Qt.UserRole))
        if text.startswith("─"):
            break

    assert "aaa000" in refs, "suggested main should use merge-base SHA, not branch label"
    assert "bbb000" in refs, "suggested feature/foo should use merge-base SHA, not branch label"


def test_suggested_branch_entries_show_merge_base_label():
    sel = DiffPointSelector()
    git = _make_git({"main": "aaa000", "feature/foo": "bbb000"})
    store = _make_store("merge_base")
    sel.set_repo(
        "/repo", _make_points(), git_service=git, config_store=store,
        suggested_older=["main", "feature/foo"],
    )

    labels = []
    for i in range(sel._older_list.count()):
        item = sel._older_list.item(i)
        text = item.text() if item else ""
        if text.startswith("★") or text.startswith("─"):
            continue
        labels.append(text)

    assert any("main (merge base)" in l for l in labels)
    assert any("feature/foo (merge base)" in l for l in labels)
