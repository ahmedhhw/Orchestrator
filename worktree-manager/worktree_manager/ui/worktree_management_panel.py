from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
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
        on_diff_from_working_tree=None,
        on_diff_compare_branches=None,
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
        self._on_diff_from_working_tree = on_diff_from_working_tree
        self._on_diff_compare_branches = on_diff_compare_branches
        self._repo_view: QWidget | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ── toolbar row ───────────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self._repo_combo = QComboBox()
        self._repo_combo.setObjectName("repo_combo")
        self._repo_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar.addWidget(QLabel("Repo:"))
        toolbar.addWidget(self._repo_combo, 1)

        add_btn = QPushButton("+ Add Repo")
        add_btn.clicked.connect(self._on_add_repo)
        toolbar.addWidget(add_btn)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self._handle_refresh)
        toolbar.addWidget(refresh_btn)

        outer.addLayout(toolbar)

        # ── repo view area ────────────────────────────────────────────────────
        self._view_area = QVBoxLayout()
        self._view_area.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._view_area, 1)

        self._empty_label = QLabel("Select a repo above, or click + Add Repo to register one.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: gray; font-size: 14px;")
        self._empty_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._view_area.addWidget(self._empty_label)

        self._populate_repos()
        self._repo_combo.currentIndexChanged.connect(self._on_repo_combo_changed)

    def _populate_repos(self):
        self._repo_combo.blockSignals(True)
        self._repo_combo.clear()
        for path in self._vm.list_repos():
            self._repo_combo.addItem(Path(path).name, userData=path)
        self._repo_combo.blockSignals(False)

        selected = self._vm.selected_repo()
        if selected:
            idx = self._repo_combo.findData(selected)
            if idx >= 0:
                self._repo_combo.setCurrentIndex(idx)
                self._show_repo_view(selected)
                return

        if self._repo_combo.count() > 0:
            self._show_repo_view(self._repo_combo.itemData(0))
        else:
            self._show_empty()

    def _on_repo_combo_changed(self, index: int):
        repo_path = self._repo_combo.itemData(index)
        if repo_path:
            self._vm.select_repo(repo_path)
            self._show_repo_view(repo_path)

    def _show_repo_view(self, repo_path: str):
        self._empty_label.setVisible(False)

        if self._repo_view is not None:
            self._view_area.removeWidget(self._repo_view)
            self._repo_view.deleteLater()
            self._repo_view = None

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
            on_diff_from_working_tree=self._on_diff_from_working_tree,
            on_diff_compare_branches=self._on_diff_compare_branches,
        )
        self._view_area.addWidget(view)
        self._repo_view = view

    def _show_empty(self):
        self._empty_label.setVisible(True)

    def _handle_refresh(self):
        self._populate_repos()
        self._on_refresh()
        if self._repo_view is not None and hasattr(self._repo_view, "refresh"):
            self._repo_view.refresh()

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

    def populate_repos(self):
        self._populate_repos()

    def refresh(self):
        self._populate_repos()
        if self._repo_view is not None and hasattr(self._repo_view, "refresh"):
            self._repo_view.refresh()
