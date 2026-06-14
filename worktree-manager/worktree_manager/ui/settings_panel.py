from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from worktree_manager.ui.filterable_combo import FilterableComboBox

from worktree_manager.setup_settings_vm import SettingsViewModel


class SettingsDialog(QDialog):
    def __init__(self, parent, vm: SettingsViewModel, store=None):
        # Accept either a real QWidget or any object (e.g. MagicMock in tests).
        # Pass a valid Qt parent to QDialog; keep the original as _app for
        # calling apply_spotlight_shortcut after Save.
        qt_parent = parent if isinstance(parent, QWidget) else None
        super().__init__(qt_parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self._vm = vm
        self._store = store
        self._app = parent          # may be App, QWidget, or MagicMock
        self._capturing = False     # True while in shortcut-record mode

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(8)

        title = QLabel("Settings")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        outer.addWidget(title)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Stale threshold:"))
        self._stale_spin = QSpinBox()
        self._stale_spin.setRange(1, 3650)
        self._stale_spin.setValue(int(vm.stale_days))
        row2.addWidget(self._stale_spin)
        row2.addWidget(QLabel("days"))
        row2.addStretch(1)
        outer.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Shell:"))
        self._shell_combo = FilterableComboBox()
        self._shell_combo.addItems(["zsh", "bash"])
        current_shell = store.get_ui_pref("shell", "zsh") if store else "zsh"
        idx = self._shell_combo.findText(current_shell)
        self._shell_combo.setCurrentIndex(idx if idx >= 0 else 0)
        row3.addWidget(self._shell_combo)
        row3.addStretch(1)
        outer.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Default editor:"))
        self._editor_combo = FilterableComboBox()
        self._editor_combo.addItem("Cursor", userData="cursor")
        self._editor_combo.addItem("VS Code", userData="vscode")
        current_editor = store.get_ui_pref("editor", "cursor") if store else "cursor"
        editor_idx = self._editor_combo.findData(current_editor)
        self._editor_combo.setCurrentIndex(editor_idx if editor_idx >= 0 else 0)
        row4.addWidget(self._editor_combo)
        row4.addStretch(1)
        outer.addLayout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Branch diff mode:"))
        self._branch_diff_combo = FilterableComboBox()
        self._branch_diff_combo.addItem("Merge base (default)", userData="merge_base")
        self._branch_diff_combo.addItem("Branch tip", userData="branch_tip")
        current_mode = store.get_branch_diff_mode() if store else "merge_base"
        mode_idx = self._branch_diff_combo.findData(current_mode)
        self._branch_diff_combo.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
        row5.addWidget(self._branch_diff_combo)
        row5.addStretch(1)
        outer.addLayout(row5)

        row6 = QHBoxLayout()
        row6.addWidget(QLabel("GitHub polling:"))
        self._github_poll_spin = QSpinBox()
        self._github_poll_spin.setRange(5, 3600)
        current_poll = store.get_github_poll_interval() if store else 30
        self._github_poll_spin.setValue(current_poll)
        row6.addWidget(self._github_poll_spin)
        row6.addWidget(QLabel("seconds"))
        row6.addStretch(1)
        outer.addLayout(row6)

        self._experimental_check = QCheckBox("Enable experimental features")
        current_experimental = store.get_experimental_features() if store else False
        self._experimental_check.setChecked(current_experimental)
        outer.addWidget(self._experimental_check)

        # ── Spotlight shortcut row ──────────────────────────────────────────
        row_sc = QHBoxLayout()
        row_sc.addWidget(QLabel("Spotlight shortcut:"))
        self._shortcut_field = QLineEdit()
        self._shortcut_field.setReadOnly(True)
        _sc = store.get_spotlight_shortcut() if store else None
        current_sc = _sc if isinstance(_sc, str) else "Ctrl+K"
        self._shortcut_field.setText(current_sc)
        row_sc.addWidget(self._shortcut_field)
        self._record_btn = QPushButton("Record")
        self._record_btn.clicked.connect(self._toggle_capture)
        row_sc.addWidget(self._record_btn)
        outer.addLayout(row_sc)

        self._shortcut_status = QLabel("Global ●")
        outer.addWidget(self._shortcut_status)

        # ── Buttons ─────────────────────────────────────────────────────────
        btns = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addStretch(1)
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._save)
        btns.addWidget(self._save_btn)
        outer.addLayout(btns)

    # ------------------------------------------------------------------
    # Shortcut capture
    # ------------------------------------------------------------------

    def _toggle_capture(self) -> None:
        """Enter / exit shortcut-record mode."""
        self._capturing = not self._capturing
        if self._capturing:
            self._record_btn.setText("Cancel")
            self._shortcut_status.setText("Press a shortcut…")
            self.installEventFilter(self)
        else:
            self._record_btn.setText("Record")
            self.removeEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if self._capturing and event.type() == QKeyEvent.Type.KeyPress:
            key_event = event  # QKeyEvent
            key = key_event.key()

            # Esc cancels capture without changing the combo
            if key == Qt.Key.Key_Escape:
                self._toggle_capture()
                return True

            # Ignore bare modifier key-presses
            if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
                       Qt.Key.Key_Meta, Qt.Key.Key_Super_L, Qt.Key.Key_Super_R):
                return True

            modifiers = key_event.modifiers()
            if modifiers == Qt.KeyboardModifier.NoModifier:
                # Bare key — reject and show message
                self._shortcut_status.setText("⚠ Needs a modifier (e.g. Ctrl+K)")
                return True

            # Build a combo string and accept
            combo = QKeySequence(modifiers | key).toString()
            if combo:
                self._shortcut_field.setText(combo)
                self._shortcut_status.setText("Global ●")
            self._toggle_capture()
            return True

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self):
        self._vm.save(
            worktree_storage=self._vm.worktree_storage,
            stale_days=int(self._stale_spin.value()),
        )
        if self._store:
            self._store.set_ui_pref("shell", self._shell_combo.currentText())
            self._store.set_ui_pref("editor", self._editor_combo.currentData())
            self._store.set_branch_diff_mode(self._branch_diff_combo.currentData())
            self._store.save_github_poll_interval(int(self._github_poll_spin.value()))
            self._store.set_experimental_features(self._experimental_check.isChecked())

            # Persist the shortcut and apply it to the App window
            combo = self._shortcut_field.text()
            self._store.set_spotlight_shortcut(combo)
            if hasattr(self._app, "apply_spotlight_shortcut"):
                ok = self._app.apply_spotlight_shortcut(combo)
                if not ok:
                    self._shortcut_status.setText(
                        "⚠ Could not register globally — Local only"
                    )

        self.accept()
