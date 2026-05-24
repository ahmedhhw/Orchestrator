from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class Sidebar(QWidget):
    def __init__(
        self,
        store,
        on_command_center,
        on_workspace_projects,
        on_add_repo,
        on_refresh,
        on_repo_selected,
        on_repo_delete,
        active_repo_path=None,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._on_repo_selected = on_repo_selected
        self._on_repo_delete = on_repo_delete
        self._active_repo_path = active_repo_path
        self._repo_buttons: dict = {}

        self.setFixedWidth(220)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 8, 4, 12)
        outer.setSpacing(4)

        cc_btn = QPushButton("⊞ Command Center")
        cc_btn.clicked.connect(on_command_center)
        outer.addWidget(cc_btn)

        wp_btn = QPushButton("⊞ Workspace Projects")
        wp_btn.clicked.connect(on_workspace_projects)
        outer.addWidget(wp_btn)

        self._collapsed = bool(store.get_ui_pref("repos_collapsed", False))
        arrow = "▶" if self._collapsed else "▼"
        self._header_btn = QPushButton(f"{arrow} REPOS")
        self._header_btn.setFlat(True)
        self._header_btn.setStyleSheet(
            "text-align: left; color: gray; font-weight: bold;"
        )
        self._header_btn.clicked.connect(self.toggle_repos_section)
        outer.addWidget(self._header_btn)

        self._repo_scroll = QScrollArea()
        self._repo_scroll.setWidgetResizable(True)
        self._repo_scroll.setFixedHeight(220)
        self._repo_container = QWidget()
        self._repo_layout = QVBoxLayout(self._repo_container)
        self._repo_layout.setContentsMargins(0, 0, 0, 0)
        self._repo_layout.setSpacing(2)
        self._repo_layout.addStretch(1)
        self._repo_scroll.setWidget(self._repo_container)
        outer.addWidget(self._repo_scroll)
        self._repo_scroll.setVisible(not self._collapsed)

        outer.addStretch(1)

        add_btn = QPushButton("+ Add Repo")
        add_btn.clicked.connect(on_add_repo)
        outer.addWidget(add_btn)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(on_refresh)
        outer.addWidget(refresh_btn)

        self.populate_repo_rows()

    def populate_repo_rows(self):
        while self._repo_layout.count():
            item = self._repo_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._repo_buttons.clear()

        for path in self._store.all_repos().keys():
            name = Path(path).name
            is_active = (path == self._active_repo_path)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            label = ("● " if is_active else "○ ") + name
            btn = QPushButton(label)
            btn.setStyleSheet("text-align: left;")
            btn.clicked.connect(
                lambda _checked=False, p=path: self._on_repo_selected(p)
            )
            row_layout.addWidget(btn, 1)

            del_btn = QPushButton("✕")
            del_btn.setFixedWidth(28)
            del_btn.setStyleSheet(
                "background-color: #c0392b; color: white; border: none;"
            )
            del_btn.clicked.connect(
                lambda _checked=False, p=path: self._on_repo_delete(p)
            )
            row_layout.addWidget(del_btn)

            self._repo_layout.addWidget(row)
            self._repo_buttons[path] = btn

        self._repo_layout.addStretch(1)

    def set_active_repo(self, repo_path):
        self._active_repo_path = repo_path
        self.populate_repo_rows()

    def repos_visible(self):
        return not self._collapsed

    def toggle_repos_section(self):
        self._collapsed = not self._collapsed
        self._store.set_ui_pref("repos_collapsed", self._collapsed)
        arrow = "▶" if self._collapsed else "▼"
        self._header_btn.setText(f"{arrow} REPOS")
        self._repo_scroll.setVisible(not self._collapsed)
