"""Tests for InlineProgress — reusable loading widget with QProgressBar."""
from PySide6.QtWidgets import QProgressBar, QLabel


def test_indeterminate_mode_sets_marquee_range(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress

    w = InlineProgress()
    qtbot.addWidget(w)
    w.start_indeterminate("Loading…")

    bar = w.findChild(QProgressBar)
    assert bar is not None
    assert bar.minimum() == 0
    assert bar.maximum() == 0


def test_indeterminate_mode_shows_message(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress

    w = InlineProgress()
    qtbot.addWidget(w)
    w.start_indeterminate("Fetching repos…")

    texts = [lbl.text() for lbl in w.findChildren(QLabel)]
    assert any("Fetching repos" in t for t in texts)


def test_determinate_mode_sets_bar_range(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress

    w = InlineProgress()
    qtbot.addWidget(w)
    w.start_determinate("Scanning…", total=10)

    bar = w.findChild(QProgressBar)
    assert bar.minimum() == 0
    assert bar.maximum() == 10
    assert bar.value() == 0


def test_determinate_mode_shows_message(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress

    w = InlineProgress()
    qtbot.addWidget(w)
    w.start_determinate("Scanning branches…", total=5)

    texts = [lbl.text() for lbl in w.findChildren(QLabel)]
    assert any("Scanning branches" in t for t in texts)


def test_update_advances_bar_value(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress

    w = InlineProgress()
    qtbot.addWidget(w)
    w.start_determinate("Loading…", total=8)
    w.update(3, "feature/x")

    bar = w.findChild(QProgressBar)
    assert bar.value() == 3


def test_update_shows_detail_label(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress

    w = InlineProgress()
    qtbot.addWidget(w)
    w.start_determinate("Loading…", total=8)
    w.update(3, "feature/billing")

    texts = [lbl.text() for lbl in w.findChildren(QLabel)]
    assert any("feature/billing" in t for t in texts)


def test_reset_does_not_raise(qtbot):
    from worktree_manager.ui.inline_progress import InlineProgress

    w = InlineProgress()
    qtbot.addWidget(w)
    w.start_indeterminate("Loading…")
    w.reset()
