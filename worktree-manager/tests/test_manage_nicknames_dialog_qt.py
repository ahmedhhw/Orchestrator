from PySide6.QtWidgets import QPushButton, QLabel
from worktree_manager.spotlight.nickname_store import NicknameEntry, NicknameStore
from worktree_manager.ui.manage_nicknames_dialog import ManageNicknamesDialog


class _FakeConfigStore:
    def __init__(self):
        self._prefs: dict = {}

    def get_ui_pref(self, key, default=None):
        return self._prefs.get(key, default)

    def set_ui_pref(self, key, value) -> None:
        self._prefs[key] = value


def _make_store(*entries: NicknameEntry) -> NicknameStore:
    cs = _FakeConfigStore()
    store = NicknameStore(cs)
    for e in entries:
        store.save(e)
    return store


def test_dialog_shows_empty_label_when_no_nicknames(qtbot):
    store = _make_store()
    dlg = ManageNicknamesDialog(parent=None, nickname_store=store)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg._empty_label.isVisible()
    assert not dlg._scroll.isVisible()


def test_dialog_shows_nicknames(qtbot):
    store = _make_store(
        NicknameEntry("devsir", "run_command", {"repo": "dev", "worktree": "main", "cmd": "runserver"}),
        NicknameEntry("myproj", "open_project", {"name": "alpha"}),
    )
    dlg = ManageNicknamesDialog(parent=None, nickname_store=store)
    qtbot.addWidget(dlg)
    dlg.show()
    assert not dlg._empty_label.isVisible()
    assert dlg._scroll.isVisible()
    labels = dlg.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("devsir" in t for t in texts)
    assert any("myproj" in t for t in texts)


def test_delete_button_removes_nickname(qtbot):
    store = _make_store(
        NicknameEntry("devsir", "run_command", {"repo": "dev", "worktree": "main", "cmd": "runserver"}),
    )
    dlg = ManageNicknamesDialog(parent=None, nickname_store=store)
    qtbot.addWidget(dlg)
    dlg.show()

    del_btn = dlg.findChild(QPushButton, "del_btn_devsir")
    assert del_btn is not None
    qtbot.mouseClick(del_btn, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)

    assert store.get("devsir") is None
    assert dlg.nickname_count() == 0


def test_delete_updates_ui_to_empty_state(qtbot):
    store = _make_store(NicknameEntry("n1", "open_project", {"name": "alpha"}))
    dlg = ManageNicknamesDialog(parent=None, nickname_store=store)
    qtbot.addWidget(dlg)
    dlg.show()

    del_btn = dlg.findChild(QPushButton, "del_btn_n1")
    qtbot.mouseClick(del_btn, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)

    assert dlg._empty_label.isVisible()
    assert not dlg._scroll.isVisible()


def test_delete_one_of_many_leaves_rest(qtbot):
    store = _make_store(
        NicknameEntry("a", "open_project", {"name": "alpha"}),
        NicknameEntry("b", "open_project", {"name": "beta"}),
    )
    dlg = ManageNicknamesDialog(parent=None, nickname_store=store)
    qtbot.addWidget(dlg)
    dlg.show()

    del_btn = dlg.findChild(QPushButton, "del_btn_a")
    qtbot.mouseClick(del_btn, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.LeftButton)

    assert store.get("a") is None
    assert store.get("b") is not None
    assert dlg.nickname_count() == 1


def test_nickname_action_and_args_shown_in_label(qtbot):
    store = _make_store(
        NicknameEntry("devsir", "run_command", {"repo": "dev", "worktree": "main", "cmd": "runserver"}),
    )
    dlg = ManageNicknamesDialog(parent=None, nickname_store=store)
    qtbot.addWidget(dlg)
    dlg.show()

    label = dlg.findChild(QLabel, "nick_label_devsir")
    assert label is not None
    assert "run_command" in label.text()
    assert "runserver" in label.text()
