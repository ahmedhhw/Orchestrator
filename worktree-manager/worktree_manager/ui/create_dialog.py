from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

from worktree_manager.ui.filterable_combo import FilterableComboBox


class _StringVar:
    """Tiny tk-style facade so existing tests calling ._mode_var.set/get keep working."""
    def __init__(self, initial=""):
        self._value = initial
        self._on_change = None

    def set(self, value):
        self._value = value
        if self._on_change:
            self._on_change(value)

    def get(self):
        return self._value


class _EntryFacade:
    """LineEdit wrapper providing tk-style insert/delete/get for test compatibility."""
    def __init__(self, line_edit: QLineEdit):
        self._le = line_edit

    def insert(self, index, text):
        if index == 0:
            self._le.setText(text + self._le.text())
        else:
            cur = self._le.text()
            self._le.setText(cur[:index] + text + cur[index:])

    def delete(self, first, last=None):
        self._le.clear()

    def clear(self):
        self._le.clear()

    def get(self):
        return self._le.text()


class CreateDialog(QDialog):
    def __init__(self, parent, branches: list, existing_branches: list, on_create):
        super().__init__(parent)
        self.setWindowTitle("New Worktree")
        self.setModal(True)
        self._branches = branches
        self._existing_branches = existing_branches
        self._on_create = on_create

        self._mode_var = _StringVar("new")
        self._mode_var._on_change = lambda _v: self._on_mode_change()

        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(8)

        mode_row = QHBoxLayout()
        self._new_radio = QRadioButton("New branch")
        self._new_radio.setChecked(True)
        self._new_radio.toggled.connect(
            lambda checked: checked and self._mode_var.set("new")
        )
        self._existing_radio = QRadioButton("Existing branch")
        self._existing_radio.toggled.connect(
            lambda checked: checked and self._mode_var.set("existing")
        )
        group = QButtonGroup(self)
        group.addButton(self._new_radio)
        group.addButton(self._existing_radio)
        mode_row.addWidget(self._new_radio)
        mode_row.addWidget(self._existing_radio)
        mode_row.addStretch(1)
        outer.addLayout(mode_row)

        # ── New branch frame ────────────────────────────────────────────────
        self._new_frame = QWidget()
        new_layout = QVBoxLayout(self._new_frame)
        new_layout.setContentsMargins(0, 0, 0, 0)
        new_layout.setSpacing(4)

        new_layout.addWidget(QLabel("Worktree name:"))
        wt_row = QHBoxLayout()
        self._wt_name_le = QLineEdit()
        self._wt_name_le.setPlaceholderText("fix-login")
        self._wt_name_le.setMinimumWidth(240)
        wt_row.addWidget(self._wt_name_le)
        copy_b2w = QPushButton("← copy from branch")
        copy_b2w.setFixedWidth(150)
        copy_b2w.clicked.connect(self._copy_branch_to_wt)
        wt_row.addWidget(copy_b2w)
        new_layout.addLayout(wt_row)

        new_layout.addSpacing(6)
        new_layout.addWidget(QLabel("Branch name:"))
        br_row = QHBoxLayout()
        self._branch_le = QLineEdit()
        self._branch_le.setPlaceholderText("fix/")
        self._branch_le.setMinimumWidth(240)
        br_row.addWidget(self._branch_le)
        copy_w2b = QPushButton("← copy from worktree")
        copy_w2b.setFixedWidth(150)
        copy_w2b.clicked.connect(self._copy_wt_to_branch)
        br_row.addWidget(copy_w2b)
        new_layout.addLayout(br_row)

        new_layout.addSpacing(6)
        new_layout.addWidget(QLabel("Base branch:"))
        self._base_combo = FilterableComboBox()
        self._base_combo.addItems(self._branches or ["main"])
        self._base_var = _StringVar(self._branches[0] if self._branches else "main")
        self._base_combo.currentIndexChanged.connect(
            lambda _: self._base_var.set(self._base_combo.currentText())
        )
        self._base_var._on_change = self._base_combo.setCurrentText
        new_layout.addWidget(self._base_combo)

        outer.addWidget(self._new_frame)

        # ── Existing branch frame ───────────────────────────────────────────
        self._existing_frame = QWidget()
        ex_layout = QVBoxLayout(self._existing_frame)
        ex_layout.setContentsMargins(0, 0, 0, 0)
        ex_layout.setSpacing(4)

        ex_layout.addWidget(QLabel("Existing branch:"))
        self._existing_combo = QComboBox()
        self._existing_combo.addItems(self._existing_branches or ["(none available)"])
        self._existing_var = _StringVar(
            self._existing_branches[0] if self._existing_branches else ""
        )
        self._existing_combo.currentTextChanged.connect(self._existing_var.set)
        self._existing_var._on_change = self._existing_combo.setCurrentText
        ex_layout.addWidget(self._existing_combo)

        ex_layout.addSpacing(6)
        ex_layout.addWidget(QLabel("Worktree name:"))
        ex_wt_row = QHBoxLayout()
        self._existing_wt_name_le = QLineEdit()
        self._existing_wt_name_le.setPlaceholderText("fix-login")
        self._existing_wt_name_le.setMinimumWidth(240)
        ex_wt_row.addWidget(self._existing_wt_name_le)
        copy_ex = QPushButton("← copy from branch")
        copy_ex.setFixedWidth(150)
        copy_ex.clicked.connect(self._copy_existing_branch_to_wt)
        ex_wt_row.addWidget(copy_ex)
        ex_layout.addLayout(ex_wt_row)

        outer.addWidget(self._existing_frame)

        # tk-facade entry adapters so existing tests using insert/delete/get pass
        self._wt_name_entry = _EntryFacade(self._wt_name_le)
        self._branch_entry = _EntryFacade(self._branch_le)
        self._existing_wt_name_entry = _EntryFacade(self._existing_wt_name_le)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        create = QPushButton("Create")
        create.clicked.connect(self._create)
        btns.addWidget(create)
        outer.addLayout(btns)

        self._on_mode_change()

    def _on_mode_change(self):
        is_new = self._mode_var.get() == "new"
        if is_new and not self._new_radio.isChecked():
            self._new_radio.setChecked(True)
        if not is_new and not self._existing_radio.isChecked():
            self._existing_radio.setChecked(True)
        self._new_frame.setVisible(is_new)
        self._existing_frame.setVisible(not is_new)

    def _copy_branch_to_wt(self):
        branch = self._branch_le.text().strip()
        self._wt_name_le.setText(branch.replace("/", "-"))

    def _copy_wt_to_branch(self):
        wt_name = self._wt_name_le.text().strip()
        self._branch_le.setText(wt_name.replace("-", "/", 1))

    def _copy_existing_branch_to_wt(self):
        branch = self._existing_var.get()
        self._existing_wt_name_le.setText(branch.replace("/", "-"))

    def _create(self):
        if self._mode_var.get() == "existing":
            branch = self._existing_var.get()
            if not branch or branch == "(none available)":
                return
            wt_name = self._existing_wt_name_le.text().strip() or None
            self._on_create(branch, None, True, wt_name)
        else:
            branch = self._branch_le.text().strip()
            if not branch:
                return
            wt_name = self._wt_name_le.text().strip() or None
            self._on_create(branch, self._base_var.get(), False, wt_name)
        self.accept()
