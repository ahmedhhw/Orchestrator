from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from worktree_manager.ui.per_repo_worktrees_view import PerRepoWorktreesView
from worktree_manager.worktree_mgmt_vm import WorktreeMgmtViewModel


class WorktreeManagementPanel(QWidget):
    def __init__(
        self,
        vm: WorktreeMgmtViewModel,
        on_add_repo,
        on_refresh,
        on_cleanup,
        on_new_worktree=None,
        on_generate_project=None,
        on_run_command=None,
        on_nickname=None,
        parent=None,
    ):
        super().__init__(parent)
        self._vm = vm
        self._on_add_repo = on_add_repo
        self._on_refresh = on_refresh
        self._on_cleanup = on_cleanup
        self._on_new_worktree = on_new_worktree
        self._on_generate_project = on_generate_project
        self._on_run_command = on_run_command
        self._on_nickname = on_nickname
        self._repo_buttons: dict[str, QPushButton] = {}
        self._right_pane: QWidget | None = None

        splitter = QSplitter(Qt.Horizontal, self)

        # ── left pane ──────────────────────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(160)
        left.setMaximumWidth(260)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 8, 4, 8)
        left_layout.setSpacing(4)

        repos_label = QLabel("Repos")
        repos_label.setStyleSheet("font-weight: bold; color: gray;")
        left_layout.addWidget(repos_label)

        self._repo_scroll = QScrollArea()
        self._repo_scroll.setWidgetResizable(True)
        self._repo_container = QWidget()
        self._repo_layout = QVBoxLayout(self._repo_container)
        self._repo_layout.setContentsMargins(0, 0, 0, 0)
        self._repo_layout.setSpacing(2)
        self._repo_layout.addStretch(1)
        self._repo_scroll.setWidget(self._repo_container)
        left_layout.addWidget(self._repo_scroll, 1)

        add_btn = QPushButton("+ Add Repo")
        add_btn.clicked.connect(self._on_add_repo)
        left_layout.addWidget(add_btn)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self._handle_refresh)
        left_layout.addWidget(refresh_btn)

        splitter.addWidget(left)

        # ── right pane ─────────────────────────────────────────────────────────
        self._right_container = QWidget()
        right_layout = QVBoxLayout(self._right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._empty_label = QLabel("Select a repo on the left, or click + Add Repo to register one.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: gray; font-size: 14px;")
        self._empty_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self._empty_label)
        splitter.addWidget(self._right_container)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)

        self.populate_repos()
        # Auto-show pre-selected repo from VM
        if self._vm.selected_repo():
            self._show_repo_view(self._vm.selected_repo())

    def populate_repos(self):
        while self._repo_layout.count():
            item = self._repo_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._repo_buttons.clear()

        selected = self._vm.selected_repo()
        for path in self._vm.list_repos():
            name = Path(path).name
            is_active = (path == selected)
            label = ("● " if is_active else "○ ") + name
            btn = QPushButton(label)
            btn.setStyleSheet("text-align: left;")
            btn.clicked.connect(lambda _checked=False, p=path: self._select_repo(p))
            if self._on_nickname is not None:
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, n=name, b=btn: self._show_repo_nickname_menu(b, n)
                )
            self._repo_layout.addWidget(btn)
            self._repo_buttons[path] = btn

        self._repo_layout.addStretch(1)

    def _select_repo(self, repo_path: str):
        self._vm.select_repo(repo_path)
        self.populate_repos()
        self._show_repo_view(repo_path)

    def _show_repo_view(self, repo_path: str):
        self._empty_label.setVisible(False)

        if self._right_pane is not None:
            self._right_container.layout().removeWidget(self._right_pane)
            self._right_pane.deleteLater()
            self._right_pane = None

        repo_vm = self._vm.per_repo_vm(repo_path)
        repo_name = Path(repo_path).name

        view = PerRepoWorktreesView(
            vm=repo_vm,
            repo_name=repo_name,
            on_cleanup=lambda: self._on_cleanup(repo_path),
            on_new=lambda: (self._on_new_worktree(repo_vm) if self._on_new_worktree else None),
            on_generate_project=self._on_generate_project,
            on_run_command=self._on_run_command,
            on_nickname=self._on_nickname,
        )
        self._right_container.layout().addWidget(view)
        self._right_pane = view

    def _handle_refresh(self):
        self.populate_repos()
        self._on_refresh()
        if self._right_pane is not None and hasattr(self._right_pane, "refresh"):
            self._right_pane.refresh()

    def _show_repo_nickname_menu(self, btn: QPushButton, repo_name: str) -> None:
        menu = QMenu(self)
        menu.addAction("Add Nickname for 'repo'…").triggered.connect(
            lambda: self._on_nickname("focus_repo", {"name": repo_name})
        )
        menu.addAction("Add Nickname for 'cleanup'…").triggered.connect(
            lambda: self._on_nickname("cleanup_repo", {"name": repo_name})
        )
        menu.addAction("Add Nickname for 'delete repo'…").triggered.connect(
            lambda: self._on_nickname("delete_repo", {"name": repo_name})
        )
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def refresh(self):
        self.populate_repos()
        if self._right_pane is not None and hasattr(self._right_pane, "refresh"):
            self._right_pane.refresh()
