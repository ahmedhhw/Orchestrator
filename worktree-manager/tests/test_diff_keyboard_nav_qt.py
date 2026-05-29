from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from worktree_manager.ui.diff_file_list import DiffFileList
from worktree_manager.ui.diff_hunk_view import DiffHunkView
from worktree_manager.diff_models import DiffFile, DiffHunk


def _make_files():
    return [
        DiffFile(path="a.py", status="M"),
        DiffFile(path="b.py", status="M"),
        DiffFile(path="c.py", status="A"),
    ]


def _make_hunks():
    return [
        DiffHunk(index=0, header="@@ -1,4 +1,4 @@", lines=[" ctx", "-old", "+new", " ctx"],
                 old_start=1, old_count=4, new_start=1, new_count=4),
    ]


def _press(widget, key, modifier=Qt.NoModifier):
    ev = QKeyEvent(QEvent.KeyPress, key, modifier)
    QApplication.sendEvent(widget, ev)


def _make_file_list(qtbot):
    fl = DiffFileList()
    qtbot.addWidget(fl)
    fl.set_files(_make_files())
    fl._list_widget.setCurrentRow(0)
    return fl


def _make_hunk_view(qtbot):
    hv = DiffHunkView()
    qtbot.addWidget(hv)
    hv.set_hunks("a.py", _make_hunks(), live_mode=False)
    return hv


# ── DiffFileList: select_next / select_prev ───────────────────────────────────

def test_select_next_moves_down(qtbot):
    fl = _make_file_list(qtbot)
    fl.select_next()
    assert fl._list_widget.currentRow() == 1


def test_select_prev_moves_up(qtbot):
    fl = _make_file_list(qtbot)
    fl._list_widget.setCurrentRow(1)
    fl.select_prev()
    assert fl._list_widget.currentRow() == 0


def test_select_next_wraps_to_first(qtbot):
    fl = _make_file_list(qtbot)
    fl._list_widget.setCurrentRow(2)
    fl.select_next()
    assert fl._list_widget.currentRow() == 0


def test_select_prev_wraps_to_last(qtbot):
    fl = _make_file_list(qtbot)
    fl._list_widget.setCurrentRow(0)
    fl.select_prev()
    assert fl._list_widget.currentRow() == 2


# ── DiffFileList key events ───────────────────────────────────────────────────

def test_down_key_selects_next_file(qtbot):
    fl = _make_file_list(qtbot)
    _press(fl._list_widget, Qt.Key_Down)
    assert fl._list_widget.currentRow() == 1


def test_up_key_selects_prev_file(qtbot):
    fl = _make_file_list(qtbot)
    fl._list_widget.setCurrentRow(1)
    _press(fl._list_widget, Qt.Key_Up)
    assert fl._list_widget.currentRow() == 0


def test_right_key_fires_focus_right_callback(qtbot):
    fl = _make_file_list(qtbot)
    fired = []
    fl.on_focus_right(lambda: fired.append(True))
    _press(fl._list_widget, Qt.Key_Right)
    assert fired == [True]


def test_left_key_does_not_fire_focus_right_callback(qtbot):
    fl = _make_file_list(qtbot)
    fired = []
    fl.on_focus_right(lambda: fired.append(True))
    _press(fl._list_widget, Qt.Key_Left)
    assert fired == []


def test_o_key_fires_open_file_callback_when_live(qtbot):
    fl = _make_file_list(qtbot)
    opened = []
    fl.on_open_file(lambda: opened.append(True))
    fl.set_live_mode(True)
    _press(fl._list_widget, Qt.Key_O)
    assert opened == [True]


def test_o_key_no_op_when_not_live(qtbot):
    fl = _make_file_list(qtbot)
    opened = []
    fl.on_open_file(lambda: opened.append(True))
    fl.set_live_mode(False)
    _press(fl._list_widget, Qt.Key_O)
    assert opened == []


# ── DiffHunkView key events ───────────────────────────────────────────────────

def test_left_key_fires_focus_left_callback(qtbot):
    hv = _make_hunk_view(qtbot)
    fired = []
    hv.on_focus_left(lambda: fired.append(True))
    _press(hv, Qt.Key_Left)
    assert fired == [True]


def test_right_key_does_not_fire_focus_left_callback(qtbot):
    hv = _make_hunk_view(qtbot)
    fired = []
    hv.on_focus_left(lambda: fired.append(True))
    _press(hv, Qt.Key_Right)
    assert fired == []


def test_o_key_fires_open_file_on_hunk_view_when_live(qtbot):
    hv = _make_hunk_view(qtbot)
    hv.set_hunks("a.py", _make_hunks(), live_mode=True)
    opened = []
    hv.on_open_file(lambda: opened.append(True))
    _press(hv, Qt.Key_O)
    assert opened == [True]


def test_o_key_no_op_on_hunk_view_when_not_live(qtbot):
    hv = _make_hunk_view(qtbot)
    opened = []
    hv.on_open_file(lambda: opened.append(True))
    _press(hv, Qt.Key_O)
    assert opened == []
