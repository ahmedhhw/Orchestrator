from unittest.mock import MagicMock

from PySide6.QtWidgets import QPushButton, QSplitter

from worktree_manager.ui.diff_panel import DiffPanel
from worktree_manager.ui.file_list_strip import FileListStrip


def _make_panel(qtbot):
    git = MagicMock()
    git.list_worktrees.return_value = []
    store = MagicMock()
    store.all_repos.return_value = []
    store.get_diff_pref.return_value = None
    panel = DiffPanel(git_service=git, config_store=store)
    qtbot.addWidget(panel)
    return panel


def test_diff_panel_splitter_handle_width_at_least_6(qtbot):
    panel = _make_panel(qtbot)
    assert panel._diff_splitter.handleWidth() >= 6


def test_diff_panel_collapse_hides_file_list(qtbot):
    panel = _make_panel(qtbot)
    panel._collapse_file_list()
    assert panel._file_list.isHidden()


def test_diff_panel_collapse_shows_strip(qtbot):
    panel = _make_panel(qtbot)
    panel._collapse_file_list()
    assert isinstance(panel._file_list_strip, FileListStrip)
    assert not panel._file_list_strip.isHidden()


def test_diff_panel_restore_shows_file_list(qtbot):
    panel = _make_panel(qtbot)
    panel._collapse_file_list()
    panel._restore_file_list()
    assert not panel._file_list.isHidden()


def test_diff_panel_restore_removes_strip(qtbot):
    panel = _make_panel(qtbot)
    panel._collapse_file_list()
    panel._restore_file_list()
    assert panel._file_list_strip is None


def test_diff_panel_collapse_restore_cycle_no_crash(qtbot):
    panel = _make_panel(qtbot)
    for _ in range(3):
        panel._collapse_file_list()
        panel._restore_file_list()
    assert not panel._file_list.isHidden()


def test_diff_panel_file_list_has_hide_button(qtbot):
    panel = _make_panel(qtbot)
    assert panel._file_list._hide_btn is not None
