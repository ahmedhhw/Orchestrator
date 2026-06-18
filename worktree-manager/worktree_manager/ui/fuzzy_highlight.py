"""Shared fuzzy-highlight helpers for list-view delegates.

Provides ``build_row_html`` (HTML renderer for a fuzzy-matched row) and
``FuzzyHighlightDelegate`` (a ``QStyledItemDelegate`` that re-highlights each
row using a caller-supplied needle provider).

This module must not import from ``spotlight_overlay`` to avoid a circular
dependency.  It depends only on ``worktree_manager.spotlight.fuzzy`` and
PySide6.
"""
from __future__ import annotations

from html import escape

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from worktree_manager.spotlight.fuzzy import fuzzy_match_indices

HIGHLIGHT_COLOR = "#4da3ff"


def build_row_html(text: str, needle: str) -> str:
    """Return HTML for *text* with the fuzzy-matched chars of *needle* highlighted.

    Each matched character is wrapped in a bold colored span; unmatched runs are
    HTML-escaped plain text.  With no needle (or no match) the whole string is
    rendered as escaped plain text.
    """
    matched = fuzzy_match_indices(needle, text) if needle else None
    if not matched:
        return escape(text)

    matched_set = set(matched)
    parts: list[str] = []
    for i, ch in enumerate(text):
        if i in matched_set:
            parts.append(
                f'<span style="color: {HIGHLIGHT_COLOR}; font-weight: bold;">'
                f"{escape(ch)}</span>"
            )
        else:
            parts.append(escape(ch))
    return "".join(parts)


class FuzzyHighlightDelegate(QStyledItemDelegate):
    """Renders list rows as rich text so fuzzy-matched chars can be highlighted.

    The active needle is read from *needle_provider* at paint time, so rows
    re-highlight automatically whenever the filter text changes.

    Parameters
    ----------
    parent:
        Parent QObject (typically the list widget or overlay widget).
    needle_provider:
        Zero-argument callable that returns the current needle string.
    """

    def __init__(self, parent, *, needle_provider):
        super().__init__(parent)
        self._needle_provider = needle_provider

    def _document(self, option: QStyleOptionViewItem, text: str) -> QTextDocument:
        doc = QTextDocument()
        doc.setDefaultFont(option.font)
        doc.setHtml(build_row_html(text, self._needle_provider()))
        return doc

    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""  # we draw the text ourselves below

        # Let the style paint the row background/selection without the text.
        widget_style = opt.widget.style() if opt.widget is not None else None
        if widget_style is not None:
            widget_style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        doc = self._document(opt, text)
        painter.save()
        text_rect = opt.rect
        painter.translate(text_rect.left() + 4, text_rect.top())
        doc.drawContents(painter)
        painter.restore()

    def sizeHint(self, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        doc = self._document(opt, opt.text)
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), int(doc.size().height())))
        return size
