from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QLineEdit

from worktree_manager.ui.diff_file_list import DiffFileList
from worktree_manager.diff_models import DiffFile


def _make_files():
    return [
        DiffFile(path="src/auth/login.py", status="M"),
        DiffFile(path="src/utils.py",      status="M"),
        DiffFile(path="tests/test_login.py", status="A"),
        DiffFile(path="docs/auth.md",       status="D"),
    ]


def _make_list(qtbot, files=None):
    fl = DiffFileList()
    qtbot.addWidget(fl)
    if files is not None:
        fl.set_files(files)
    return fl


# ── structure ─────────────────────────────────────────────────────────────────

def test_file_list_has_list_widget(qtbot):
    fl = _make_list(qtbot, _make_files())
    assert fl._list_widget is not None
    assert isinstance(fl._list_widget, QListWidget)


def test_file_list_has_filter_field(qtbot):
    fl = _make_list(qtbot, _make_files())
    assert isinstance(fl._filter, QLineEdit)


# ── population ────────────────────────────────────────────────────────────────

def test_set_files_shows_file_paths(qtbot):
    fl = _make_list(qtbot, _make_files())
    texts = [fl._list_widget.item(i).text() for i in range(fl._list_widget.count())]
    assert any("login.py" in t for t in texts)
    assert any("utils.py" in t for t in texts)


def test_set_files_shows_status_label(qtbot):
    fl = _make_list(qtbot, _make_files())
    texts = [fl._list_widget.item(i).text() for i in range(fl._list_widget.count())]
    assert any("[M]" in t for t in texts)
    assert any("[A]" in t for t in texts)
    assert any("[D]" in t for t in texts)


def test_set_files_count_matches_input(qtbot):
    fl = _make_list(qtbot, _make_files())
    assert fl._list_widget.count() == 4


def test_set_files_replaces_previous_list(qtbot):
    fl = _make_list(qtbot, _make_files())
    fl.set_files([DiffFile(path="only.py", status="M")])
    assert fl._list_widget.count() == 1


# ── filter ────────────────────────────────────────────────────────────────────

def test_filter_hides_non_matching_items(qtbot):
    fl = _make_list(qtbot, _make_files())
    fl._filter.setText("login")
    visible = [
        fl._list_widget.item(i).text()
        for i in range(fl._list_widget.count())
        if not fl._list_widget.item(i).isHidden()
    ]
    assert all("login" in t for t in visible)


def test_filter_shows_all_when_cleared(qtbot):
    fl = _make_list(qtbot, _make_files())
    fl._filter.setText("login")
    fl._filter.setText("")
    visible_count = sum(
        1 for i in range(fl._list_widget.count())
        if not fl._list_widget.item(i).isHidden()
    )
    assert visible_count == 4


# ── file selection callback ───────────────────────────────────────────────────

def test_on_file_selected_fires_with_file_path(qtbot):
    fl = _make_list(qtbot, _make_files())
    selected = []
    fl.on_file_selected(lambda path: selected.append(path))
    fl._list_widget.setCurrentRow(0)
    assert selected == ["src/auth/login.py"]


def test_on_file_selected_fires_each_time_row_changes(qtbot):
    fl = _make_list(qtbot, _make_files())
    selected = []
    fl.on_file_selected(lambda path: selected.append(path))
    fl._list_widget.setCurrentRow(0)
    fl._list_widget.setCurrentRow(1)
    assert len(selected) == 2
