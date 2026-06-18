"""Unit tests for the shared fuzzy-highlight module.

Tests are pure-Python where possible; the delegate tests require a QApplication
but do NOT render any windows — they only inspect the QTextDocument produced by
the delegate's internal _document() method.
"""
from html import escape

import pytest

from worktree_manager.ui.fuzzy_highlight import (
    HIGHLIGHT_COLOR,
    FuzzyHighlightDelegate,
    build_row_html,
)


# ---------------------------------------------------------------------------
# build_row_html tests
# ---------------------------------------------------------------------------

def test_build_row_html_empty_needle_returns_escaped_text():
    """Empty needle returns the HTML-escaped text with no highlight spans."""
    result = build_row_html("feature/login", "")
    assert result == escape("feature/login")
    assert "<span" not in result


def test_build_row_html_wraps_fuzzy_matched_chars_in_accent_spans():
    """For needle 'fl' in 'feature/login', f and l are wrapped in bold accent spans."""
    result = build_row_html("feature/login", "fl")
    # 'f' at index 0 and 'l' at index 8 (feature/login) are matched
    assert result.count("<span") == 2
    # The highlight color must appear in matched spans
    assert HIGHLIGHT_COLOR in result
    # font-weight bold must be set
    assert "font-weight: bold" in result
    # Unmatched text between and after must appear escaped
    assert escape("e") in result
    assert escape("a") in result


def test_build_row_html_escapes_html_special_characters_in_text():
    """Text containing < / & is escaped in both matched and unmatched runs."""
    result = build_row_html("a<b>&c", "ac")
    # No raw < > & should leak through
    assert "<b>" not in result
    assert "&c" not in result
    # Proper escapes present
    assert "&lt;" in result
    assert "&amp;" in result


def test_build_row_html_returns_escaped_plain_text_when_needle_does_not_match():
    """A non-subsequence needle produces no spans — just escaped plain text."""
    result = build_row_html("alpha", "xyz")
    assert "<span" not in result
    assert result == escape("alpha")


# ---------------------------------------------------------------------------
# FuzzyHighlightDelegate tests (requires QApplication)
# ---------------------------------------------------------------------------

def test_fuzzy_highlight_delegate_reads_live_needle_from_provider(qtbot):
    """Delegate built with a provider returning 'fl' produces HTML with a highlight span."""
    from PySide6.QtWidgets import QWidget, QStyleOptionViewItem
    from PySide6.QtGui import QFont

    needle = "fl"
    provider = lambda: needle

    parent = QWidget()
    qtbot.addWidget(parent)
    delegate = FuzzyHighlightDelegate(parent, needle_provider=provider)

    option = QStyleOptionViewItem()
    option.font = QFont()

    doc = delegate._document(option, "feature/login")
    html = doc.toHtml()
    assert HIGHLIGHT_COLOR in html


def test_fuzzy_highlight_delegate_changing_provider_output_changes_html(qtbot):
    """Changing what the provider returns changes the rendered HTML (live re-highlight)."""
    from PySide6.QtWidgets import QWidget, QStyleOptionViewItem
    from PySide6.QtGui import QFont

    current_needle = [""]  # mutable cell
    provider = lambda: current_needle[0]

    parent = QWidget()
    qtbot.addWidget(parent)
    delegate = FuzzyHighlightDelegate(parent, needle_provider=provider)

    option = QStyleOptionViewItem()
    option.font = QFont()

    # With empty needle: no highlight spans
    html_empty = delegate._document(option, "feature/login").toHtml()
    assert HIGHLIGHT_COLOR not in html_empty

    # Switch to a matching needle: highlight spans appear
    current_needle[0] = "fl"
    html_with_needle = delegate._document(option, "feature/login").toHtml()
    assert HIGHLIGHT_COLOR in html_with_needle


# ---------------------------------------------------------------------------
# Spotlight overlay still highlights rows after the import move
# ---------------------------------------------------------------------------

def test_spotlight_overlay_still_highlights_rows_after_import_move(qtbot):
    """The spotlight overlay's _row_html produces identical HTML when sourced from
    the shared module — behaviour is byte-identical to before the extraction."""
    from worktree_manager.spotlight.action_parser import ActionParser
    from worktree_manager.spotlight.action_registry import ActionRegistry, ActionSpec, ArgSlot
    from worktree_manager.ui.spotlight_overlay import SpotlightOverlay
    from worktree_manager.ui.fuzzy_highlight import build_row_html as shared_build_row_html
    from PySide6.QtWidgets import QLineEdit

    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_project",
        keywords=["project"],
        slots=[ArgSlot(name="name", candidates=lambda prev: ["feature/login"])],
        runner=lambda args: None,
    ))
    parser = ActionParser(registry)
    overlay = SpotlightOverlay(parser=parser)
    qtbot.addWidget(overlay)
    overlay.show()

    edit = overlay.findChild(QLineEdit)
    edit.setText("project fl")

    # The overlay's _row_html must match what the shared module produces
    overlay_html = overlay._row_html("feature/login")
    shared_html = shared_build_row_html("feature/login", "fl")
    assert overlay_html == shared_html
    # And it must actually contain highlights (not plain text)
    assert HIGHLIGHT_COLOR in overlay_html
