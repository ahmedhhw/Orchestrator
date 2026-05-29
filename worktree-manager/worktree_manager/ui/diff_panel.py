import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QStackedWidget, QPushButton, QSplitter,
)
from PySide6.QtCore import Qt

from worktree_manager.diff_vm import DiffViewModel
from worktree_manager.editor_service import EditorService
from worktree_manager.ui.diff_point_selector import DiffPointSelector
from worktree_manager.ui.diff_file_list import DiffFileList
from worktree_manager.ui.diff_hunk_view import DiffHunkView


class DiffPanel(QWidget):
    def __init__(self, git_service, config_store, parent=None):
        super().__init__(parent)
        self._git = git_service
        self._store = config_store
        self._vm = DiffViewModel(git_service=git_service, config_store=config_store)
        self._editor_service = EditorService(config_store=config_store)
        self._current_file_path: str | None = None

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

        # Diff view: splitter with file list on left, hunk view on right
        self._diff_splitter = QSplitter(Qt.Horizontal)
        self._diff_splitter.setHandleWidth(6)
        self._diff_splitter.setStyleSheet(
            "QSplitter::handle { background-color: #d0d0d0; }"
            "QSplitter::handle:hover { background-color: #aaa; }"
        )
        self._file_list = DiffFileList()
        self._file_list_strip = None
        self._hunk_view = DiffHunkView()
        self._diff_splitter.addWidget(self._file_list)
        self._diff_splitter.addWidget(self._hunk_view)
        self._diff_splitter.setStretchFactor(0, 1)
        self._diff_splitter.setStretchFactor(1, 2)

        self._right_area.addWidget(self._point_selector)  # index 0
        self._right_area.addWidget(self._diff_splitter)   # index 1
        layout.addWidget(self._right_area, 1)

        self._point_selector.on_compare(self._on_compare)
        self._file_list.on_hide(self._collapse_file_list)
        self._file_list.on_file_selected(self._on_file_selected)
        self._file_list.on_focus_right(self._focus_hunk_view)
        self._file_list.on_open_file(self._on_open_file)
        self._hunk_view.on_restore(self._on_restore)
        self._hunk_view.on_open_file(self._on_open_file)
        self._hunk_view.on_focus_left(self._focus_file_list)
        self._populate_repos()
        self._repo_combo.currentIndexChanged.connect(self._on_repo_changed)
        self._worktree_combo.currentIndexChanged.connect(self._on_worktree_changed)

    def _collapse_file_list(self) -> None:
        from worktree_manager.ui.file_list_strip import FileListStrip
        self._file_list.hide()
        self._file_list_strip = FileListStrip(on_restore=self._restore_file_list)
        self._diff_splitter.insertWidget(0, self._file_list_strip)

    def _restore_file_list(self) -> None:
        if self._file_list_strip is not None:
            self._file_list_strip.deleteLater()
            self._file_list_strip = None
        self._file_list.show()

    def _populate_repos(self) -> None:
        sel = self._store.get_diff_selection()
        saved_repo = sel.get("repo_path") if sel else None
        saved_wt = sel.get("worktree_path") if sel else None

        self._repo_combo.blockSignals(True)
        self._repo_combo.clear()
        for repo_path in self._store.all_repos():
            self._repo_combo.addItem(Path(repo_path).name, userData=repo_path)
        if saved_repo:
            idx = self._repo_combo.findData(saved_repo)
            if idx >= 0:
                self._repo_combo.setCurrentIndex(idx)
        self._repo_combo.blockSignals(False)

        if self._repo_combo.count() > 0:
            self._load_repo(self._repo_combo.currentData(), preferred_worktree=saved_wt)

    def _on_repo_changed(self, index: int) -> None:
        repo_path = self._repo_combo.itemData(index)
        if repo_path:
            self._load_repo(repo_path)
            self._store.set_diff_selection(repo_path, self._worktree_combo.currentData() or "")

    def _load_repo(self, repo_path: str, preferred_worktree: str | None = None) -> None:
        self._vm.set_repo(repo_path)
        self._populate_worktrees(repo_path, preferred_worktree=preferred_worktree)

    def _populate_worktrees(self, repo_path: str, preferred_worktree: str | None = None) -> None:
        self._worktree_combo.blockSignals(True)
        self._worktree_combo.clear()
        try:
            worktrees = self._git.list_worktrees(repo_path)
        except Exception:
            worktrees = []
        for wt in worktrees:
            label = "(main)" if wt.is_main else os.path.basename(wt.path)
            self._worktree_combo.addItem(label, userData=wt.path)
        if preferred_worktree:
            idx = self._worktree_combo.findData(preferred_worktree)
            if idx >= 0:
                self._worktree_combo.setCurrentIndex(idx)
        self._worktree_combo.blockSignals(False)
        if self._worktree_combo.count() > 0:
            self._load_worktree(self._worktree_combo.currentData())
        else:
            self._show_point_selector()

    def _on_worktree_changed(self, index: int) -> None:
        wt_path = self._worktree_combo.itemData(index)
        if wt_path:
            self._load_worktree(wt_path)
            self._store.set_diff_selection(self._vm.repo_path, wt_path)

    def _load_worktree(self, worktree_path: str) -> None:
        self._vm.set_worktree(worktree_path)
        self._point_selector.set_repo(worktree_path, self._vm.available_points, git_service=self._git)
        pref = self._store.get_diff_pref(self._vm.repo_path)
        if pref:
            self._point_selector.pre_select(from_ref=pref.get("from_ref"), to_ref=pref.get("to_ref"))
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
        self._store.set_diff_pref(self._vm.repo_path, base_ref, target_ref)
        files = self._vm.load_diff_files()
        self._file_list.set_files(files)
        self._file_list.set_live_mode(self._vm.target_is_working_tree)
        self._hunk_view.set_hunks("", [], live_mode=False)
        self._summary_label.setText(
            f"FROM: {base_ref}  →  TO: {target_ref}"
        )
        self._summary_bar.show()
        self._right_area.setCurrentWidget(self._diff_splitter)

    def _on_file_selected(self, file_path: str) -> None:
        self._current_file_path = file_path
        try:
            hunks = self._vm.get_diff_hunks(file_path)
        except Exception:
            hunks = []
        self._hunk_view.set_hunks(file_path, hunks, live_mode=self._vm.target_is_working_tree)

    def _on_restore(self, hunk_indices: list) -> None:
        if self._current_file_path is None:
            return
        try:
            forward_patch = self._vm.restore_hunks(self._current_file_path, hunk_indices)
        except Exception:
            return
        count = len(hunk_indices)
        label = "hunk" if count == 1 else "hunks"
        self._hunk_view.show_toast(
            f"✓ Restored {count} {label} in {self._current_file_path}",
            undo_cb=lambda: self._on_undo_restore(forward_patch),
        )
        self._file_list.set_files(self._vm.diff_files)
        self._on_file_selected(self._current_file_path)

    def _on_undo_restore(self, forward_patch: str) -> None:
        if self._current_file_path is None:
            return
        try:
            self._vm.undo_restore(self._current_file_path, forward_patch)
        except Exception:
            return
        self._file_list.set_files(self._vm.diff_files)
        self._on_file_selected(self._current_file_path)

    def _focus_hunk_view(self) -> None:
        self._hunk_view.focus()

    def _focus_file_list(self) -> None:
        self._file_list.focus()

    def _on_open_file(self) -> None:
        if self._current_file_path is None:
            return
        self._vm.open_file(self._current_file_path, self._editor_service)
