import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QStackedWidget, QPushButton,
)

from worktree_manager.diff_vm import DiffViewModel
from worktree_manager.ui.diff_point_selector import DiffPointSelector
from worktree_manager.ui.diff_file_list import DiffFileList


class DiffPanel(QWidget):
    def __init__(self, git_service, config_store, parent=None):
        super().__init__(parent)
        self._git = git_service
        self._store = config_store
        self._vm = DiffViewModel(git_service=git_service, config_store=config_store)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Repo dropdown row
        repo_row = QHBoxLayout()
        repo_row.addWidget(QLabel("Repo:"))
        self._repo_combo = QComboBox()
        self._repo_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        repo_row.addWidget(self._repo_combo, 1)
        layout.addLayout(repo_row)

        # Worktree dropdown row
        wt_row = QHBoxLayout()
        wt_row.addWidget(QLabel("Worktree:"))
        self._worktree_combo = QComboBox()
        self._worktree_combo.setObjectName("worktree_combo")
        self._worktree_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        wt_row.addWidget(self._worktree_combo, 1)
        layout.addLayout(wt_row)

        # Summary bar (shown when in file list mode)
        self._summary_bar = QWidget()
        summary_layout = QHBoxLayout(self._summary_bar)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        self._summary_label = QLabel("")
        summary_layout.addWidget(self._summary_label, 1)
        self._change_btn = QPushButton("← Change")
        self._change_btn.clicked.connect(self._show_point_selector)
        summary_layout.addWidget(self._change_btn)
        self._summary_bar.hide()
        layout.addWidget(self._summary_bar)

        # Stacked right area
        self._right_area = QStackedWidget()
        self._point_selector = DiffPointSelector()
        self._file_list = DiffFileList()
        self._right_area.addWidget(self._point_selector)  # index 0
        self._right_area.addWidget(self._file_list)        # index 1
        layout.addWidget(self._right_area, 1)

        self._point_selector.on_compare(self._on_compare)
        self._populate_repos()
        self._repo_combo.currentIndexChanged.connect(self._on_repo_changed)
        self._worktree_combo.currentIndexChanged.connect(self._on_worktree_changed)

    def _populate_repos(self) -> None:
        self._repo_combo.blockSignals(True)
        self._repo_combo.clear()
        for repo_path in self._store.all_repos():
            self._repo_combo.addItem(Path(repo_path).name, userData=repo_path)
        self._repo_combo.blockSignals(False)
        if self._repo_combo.count() > 0:
            self._load_repo(self._repo_combo.currentData())

    def _on_repo_changed(self, index: int) -> None:
        repo_path = self._repo_combo.itemData(index)
        if repo_path:
            self._load_repo(repo_path)

    def _load_repo(self, repo_path: str) -> None:
        self._vm.set_repo(repo_path)
        self._populate_worktrees(repo_path)
        # _populate_worktrees triggers _on_worktree_changed which loads points

    def _populate_worktrees(self, repo_path: str) -> None:
        self._worktree_combo.blockSignals(True)
        self._worktree_combo.clear()
        try:
            worktrees = self._git.list_worktrees(repo_path)
        except Exception:
            worktrees = []
        for wt in worktrees:
            label = "(main)" if wt.is_main else os.path.basename(wt.path)
            self._worktree_combo.addItem(label, userData=wt.path)
        self._worktree_combo.blockSignals(False)
        if self._worktree_combo.count() > 0:
            self._load_worktree(self._worktree_combo.currentData())
        else:
            self._show_point_selector()

    def _on_worktree_changed(self, index: int) -> None:
        wt_path = self._worktree_combo.itemData(index)
        if wt_path:
            self._load_worktree(wt_path)

    def _load_worktree(self, worktree_path: str) -> None:
        self._vm.set_worktree(worktree_path)
        self._point_selector.set_repo(worktree_path, self._vm.available_points)
        self._show_point_selector()

    def _show_point_selector(self) -> None:
        self._summary_bar.hide()
        self._right_area.setCurrentWidget(self._point_selector)

    def show_for_repo(self, repo_path: str, worktree_path: str | None = None) -> None:
        self._set_repo_combo(repo_path)
        self._load_repo(repo_path)
        if worktree_path is not None:
            self._set_worktree_combo(worktree_path)
            self._load_worktree(worktree_path)
        self._point_selector.pre_select(from_ref=None, to_ref=None)

    def show_diff(self, repo_path: str, to_ref: str | None,
                  from_ref: str | None = None, worktree_path: str | None = None) -> None:
        self._set_repo_combo(repo_path)
        self._load_repo(repo_path)
        if worktree_path is not None:
            self._set_worktree_combo(worktree_path)
            self._load_worktree(worktree_path)
        self._point_selector.pre_select(from_ref=from_ref, to_ref=to_ref)

    def _set_repo_combo(self, repo_path: str) -> None:
        idx = self._repo_combo.findData(repo_path)
        if idx >= 0:
            self._repo_combo.blockSignals(True)
            self._repo_combo.setCurrentIndex(idx)
            self._repo_combo.blockSignals(False)

    def _set_worktree_combo(self, worktree_path: str) -> None:
        idx = self._worktree_combo.findData(worktree_path)
        if idx >= 0:
            self._worktree_combo.blockSignals(True)
            self._worktree_combo.setCurrentIndex(idx)
            self._worktree_combo.blockSignals(False)

    def _on_compare(self, base_ref: str, target_ref: str) -> None:
        self._vm.set_points(base_ref, target_ref)
        files = self._vm.load_diff_files()
        self._file_list.set_files(files)
        self._summary_label.setText(
            f"FROM: {base_ref}  →  TO: {target_ref}"
        )
        self._summary_bar.show()
        self._right_area.setCurrentWidget(self._file_list)
