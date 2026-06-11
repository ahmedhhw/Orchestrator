"""Tests for force_light_mode helper in cli.py — Iteration 0."""
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_force_light_mode_sets_color_scheme(qt_app):
    from worktree_manager.cli import force_light_mode

    force_light_mode(qt_app)

    assert qt_app.styleHints().colorScheme() == Qt.ColorScheme.Light
