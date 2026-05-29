from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout,
)

from worktree_manager.models import WorktreeModel


class _BoolVar:
    """tk-style BooleanVar facade so tests calling ._also_branch.set/get keep working."""
    def __init__(self, initial=False):
        self._value = bool(initial)
        self._on_change = None

    def set(self, value):
        self._value = bool(value)
        if self._on_change:
            self._on_change(self._value)

    def get(self):
        return self._value


class DeleteDialog(QDialog):
    def __init__(self, parent, wt: WorktreeModel, on_delete,
                 is_protected: bool = False,
                 has_uncommitted: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Delete Worktree")
        self.setModal(True)
        self._wt = wt
        self._on_delete = on_delete
        self._is_protected = is_protected
        self._has_uncommitted = has_uncommitted
        self._also_branch = _BoolVar(False if is_protected else True)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(6)

        title = QLabel("Delete worktree?")
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        outer.addWidget(QLabel(f"Branch:  {self._wt.branch}"))
        path_label = QLabel(f"Path:    {self._wt.path}")
        path_label.setWordWrap(True)
        outer.addWidget(path_label)

        if self._has_uncommitted:
            warn = QLabel("⚠ Unstaged or uncommitted changes detected.")
            warn.setStyleSheet("color: orange;")
            warn.setAlignment(Qt.AlignCenter)
            outer.addWidget(warn)

        cb_text = (
            "Also delete branch  (protected)" if self._is_protected
            else "Also delete branch"
        )
        self._cb = QCheckBox(cb_text)
        self._cb.setChecked(self._also_branch.get())
        self._cb.toggled.connect(self._also_branch.set)
        self._also_branch._on_change = self._cb.setChecked
        if self._is_protected:
            self._cb.setEnabled(False)
        outer.addWidget(self._cb)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        confirm_label = "Delete"
        delete = QPushButton(confirm_label)
        delete.setStyleSheet("background-color: #c0392b; color: white;")
        delete.clicked.connect(self._delete)
        btns.addWidget(delete)
        outer.addLayout(btns)

    def _delete(self):
        if self._has_uncommitted:
            QMessageBox.critical(
                self, "Cannot delete branch",
                f'"{self._wt.branch}" has uncommitted changes.\n\n'
                "Commit or discard changes before deleting.",
            )
            return
        self._on_delete(self._wt, self._also_branch.get())
        self.accept()
