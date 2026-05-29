from PySide6.QtWidgets import (
    QFrame, QSizePolicy, QVBoxLayout, QPushButton, QWidget,
)


_TAB_DEFS = [
    ("workspace_projects", "📁  Projects"),
    ("cmd_center",         "⊞  Commands"),
    ("diff",               "⇄  Diff"),
    ("worktree_management","🌳  Worktrees"),
    ("branch_management",  "🌿  Branches"),
]

_ACTIVE_STYLE = (
    "QPushButton {"
    "  text-align: left;"
    "  font-weight: bold;"
    "  padding: 10px 12px;"
    "  border: 1px solid #2980b9;"
    "  border-left: 4px solid #2980b9;"
    "  border-radius: 6px;"
    "  background-color: #e8f4fd;"
    "}"
)

_INACTIVE_STYLE = (
    "QPushButton {"
    "  text-align: left;"
    "  padding: 10px 12px;"
    "  border: 1px solid #d0d0d0;"
    "  border-radius: 6px;"
    "  background-color: transparent;"
    "}"
    "QPushButton:hover {"
    "  background-color: #f5f5f5;"
    "  border-color: #bbb;"
    "}"
)

_BOTTOM_STYLE = (
    "QPushButton {"
    "  text-align: left;"
    "  padding: 10px 12px;"
    "  border: 1px solid #d0d0d0;"
    "  border-radius: 6px;"
    "  background-color: transparent;"
    "}"
    "QPushButton:hover {"
    "  background-color: #f5f5f5;"
    "  border-color: #bbb;"
    "}"
)


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return line


class Sidebar(QWidget):
    def __init__(
        self,
        store,
        on_command_center,
        on_workspace_projects,
        on_branch_management,
        on_worktree_management,
        on_settings,
        on_diff=None,
        on_refresh=None,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._callbacks = {
            "cmd_center": on_command_center,
            "workspace_projects": on_workspace_projects,
            "branch_management": on_branch_management,
            "worktree_management": on_worktree_management,
            "diff": on_diff or (lambda: None),
        }
        self._on_settings = on_settings
        self._on_refresh = on_refresh
        self._active_key: str = "workspace_projects"
        self._tab_buttons: dict[str, QPushButton] = {}

        self.setMinimumWidth(220)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 16, 10, 16)
        outer.setSpacing(6)

        for key, label in _TAB_DEFS:
            btn = QPushButton(label)
            btn.setStyleSheet(_INACTIVE_STYLE)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setFixedHeight(44)
            btn.clicked.connect(lambda _checked=False, k=key: self._activate(k))
            outer.addWidget(btn)
            self._tab_buttons[key] = btn

        outer.addStretch(1)
        outer.addWidget(_divider())
        outer.addSpacing(4)

        if on_refresh is not None:
            refresh_btn = QPushButton("↻  Refresh")
            refresh_btn.setStyleSheet(_BOTTOM_STYLE)
            refresh_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            refresh_btn.setFixedHeight(44)
            refresh_btn.clicked.connect(self._on_refresh)
            outer.addWidget(refresh_btn)

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setStyleSheet(_BOTTOM_STYLE)
        settings_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        settings_btn.setFixedHeight(44)
        settings_btn.clicked.connect(self._on_settings)
        outer.addWidget(settings_btn)

        self._apply_highlights()

    def set_active_tab(self, key: str) -> None:
        """Update the sidebar highlight without triggering the tab callback."""
        self._active_key = key
        self._apply_highlights()

    def _activate(self, key: str) -> None:
        self._active_key = key
        self._apply_highlights()
        self._callbacks[key]()

    def _apply_highlights(self) -> None:
        for key, btn in self._tab_buttons.items():
            is_active = (key == self._active_key)
            btn.setStyleSheet(_ACTIVE_STYLE if is_active else _INACTIVE_STYLE)
            btn.setProperty("active_tab", True if is_active else None)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
