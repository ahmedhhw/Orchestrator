from PySide6.QtWidgets import QLabel
from worktree_manager.ui.landing_screen import LandingScreen


def test_landing_screen_is_a_qwidget(qtbot):
    from PySide6.QtWidgets import QWidget
    w = LandingScreen()
    qtbot.addWidget(w)
    assert isinstance(w, QWidget)


def test_landing_screen_shows_empty_message(qtbot):
    w = LandingScreen()
    qtbot.addWidget(w)
    texts = [lbl.text() for lbl in w.findChildren(QLabel)]
    combined = "\n".join(texts)
    assert "No repo selected" in combined
    assert "Add Repo" in combined
