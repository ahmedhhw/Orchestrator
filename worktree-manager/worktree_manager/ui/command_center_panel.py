from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from worktree_manager.command_runner import RunHandle, RunStatus
from worktree_manager.ui.command_pane import CommandPane
from worktree_manager.ui.launch_dialog import LaunchDialog
from worktree_manager.ui.manage_commands_dialog import ManageCommandsDialog


class _VMBridge(QObject):
    """Queues VM callbacks (background threads) onto the GUI thread via signals."""
    run_added = Signal(object)
    output_received = Signal(str, str)
    status_changed = Signal(str, object)
    run_id_changed = Signal(str, str)


class CommandCenterPanel(QWidget):
    def __init__(self, parent, vm, on_close, on_nickname=None):
        super().__init__(parent)
        self._vm = vm
        self._on_close = on_close
        self._on_nickname = on_nickname
        self._panes: dict[str, CommandPane] = {}
        self._pane_shown: dict[str, bool] = {}
        self._popouts: dict[str, object] = {}
        self._maximized_id: str | None = None

        self._bridge = _VMBridge()
        self._bridge.run_added.connect(self.add_pane)
        self._bridge.output_received.connect(self.route_output)
        self._bridge.status_changed.connect(self.route_status)
        self._bridge.run_id_changed.connect(self._on_run_id_changed)

        self._build()
        self._wire_vm()
        self._restore_existing_runs()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        toolbar = QHBoxLayout()
        title = QLabel("Command Center")
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        self._notif_btn = QPushButton()
        self._notif_btn.setCheckable(True)
        self._notif_btn.setFixedWidth(36)
        enabled = bool(self._vm._store.get_ui_pref(
            "cmd_center_notifications_enabled", True
        ))
        self._notif_btn.setChecked(enabled)
        self._update_notif_btn()
        self._notif_btn.toggled.connect(self._on_notif_toggled)
        toolbar.addWidget(self._notif_btn)
        cmds_btn = QPushButton("⚙ Commands")
        cmds_btn.clicked.connect(self._open_manage_commands_dialog)
        toolbar.addWidget(cmds_btn)
        launch_btn = QPushButton("+ Launch")
        launch_btn.clicked.connect(self._open_launch_dialog)
        toolbar.addWidget(launch_btn)
        close_btn = QPushButton("×")
        close_btn.setFixedWidth(32)
        close_btn.clicked.connect(self.trigger_close)
        toolbar.addWidget(close_btn)
        outer.addLayout(toolbar)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter running commands by name or repo…")
        self._search.textChanged.connect(self._on_search_changed)
        outer.addWidget(self._search)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll_container = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_container)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(4)
        self._scroll.setWidget(self._scroll_container)
        outer.addWidget(self._scroll, 1)

        self._empty_label = QLabel(
            "No commands running.\nClick [+ Launch] to start one."
        )
        self._empty_label.setStyleSheet("color: gray;")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._scroll_layout.addWidget(self._empty_label)

        self._no_match_label = QLabel("")
        self._no_match_label.setStyleSheet("color: gray;")
        self._no_match_label.setAlignment(Qt.AlignCenter)
        self._no_match_label.setVisible(False)
        self._scroll_layout.addWidget(self._no_match_label)

        self._scroll_layout.addStretch(1)

    def _wire_vm(self):
        self._vm.on_run_added = self._bridge.run_added.emit
        self._vm.on_output = self._bridge.output_received.emit
        self._vm.on_status_changed = self._bridge.status_changed.emit
        self._vm.on_run_id_changed = self._bridge.run_id_changed.emit

    def _restore_existing_runs(self):
        for handle in self._vm.all_runs():
            self.add_pane(handle)

    # --- pane lifecycle ---

    def add_pane(self, handle: RunHandle) -> None:
        if handle.run_id in self._panes:
            return
        try:
            worktrees = self._vm.list_worktrees(handle.repo_path)
        except Exception:
            worktrees = []
        pane = CommandPane(
            parent=self._scroll_container, handle=handle,
            on_maximize=lambda p: self._open_popout(p._run_id),
            on_stop=lambda: self._vm.stop(handle.run_id),
            on_restart=lambda: self._do_restart(handle.run_id),
            on_remove=lambda: self.remove_pane(handle.run_id),
            on_nickname=self._on_nickname,
            on_change_worktree=lambda new_path, h=handle: self._change_worktree(h, new_path),
            worktrees=worktrees,
        )
        self._panes[handle.run_id] = pane
        self._pane_shown[handle.run_id] = True
        for line in handle.output_lines:
            pane.append_line(line)
        pane.set_status(handle.status)
        self._scroll_layout.insertWidget(0, pane)
        self._empty_label.setVisible(False)
        self._apply_filter()

    def remove_pane(self, run_id: str) -> None:
        self._vm.remove_run(run_id)
        popout = self._popouts.pop(run_id, None)
        if popout is not None:
            popout.close()
        pane = self._panes.pop(run_id, None)
        self._pane_shown.pop(run_id, None)
        if pane is not None:
            self._scroll_layout.removeWidget(pane)
            pane.setParent(None)
        if self._maximized_id == run_id:
            self._maximized_id = None
        if not self._panes:
            self._empty_label.setVisible(True)
            self._no_match_label.setVisible(False)
        else:
            self._apply_filter()

    def _on_run_id_changed(self, old_id: str, new_id: str) -> None:
        pane = self._panes.pop(old_id, None)
        if pane is not None:
            self._panes[new_id] = pane
            pane.update_run_id(new_id)
            pane.update_callbacks(
                on_stop=lambda: self._vm.stop(new_id),
                on_restart=lambda: self._do_restart(new_id),
                on_remove=lambda: self.remove_pane(new_id),
            )
            new_handle = self._vm.get_run(new_id)
            if new_handle:
                for line in new_handle.output_lines:
                    pane.append_line(line)
        popout = self._popouts.pop(old_id, None)
        if popout is not None:
            self._popouts[new_id] = popout

    def _change_worktree(self, handle: RunHandle, new_worktree_path: str) -> None:
        run_id = handle.run_id
        meta = self._vm._runner._handles.get(run_id)
        self.remove_pane(run_id)
        try:
            self._vm.launch(
                repo_path=handle.repo_path,
                repo_name=handle.repo_name,
                cmd_name=handle.cmd_name,
                command_str=handle.command,
                worktree_path=new_worktree_path,
            )
        except Exception:
            pass

    def _do_restart(self, run_id: str) -> None:
        pane = self._panes.get(run_id)
        if pane is not None:
            pane.clear_output()
            pane.set_status(RunStatus.RUNNING)
        popout = self._popouts.get(run_id)
        if popout is not None:
            popout.clear_output()
            popout.set_status(RunStatus.RUNNING)
        self._vm.restart(run_id)

    def route_output(self, run_id: str, line: str) -> None:
        pane = self._panes.get(run_id)
        if pane is not None:
            pane.append_line(line)
        popout = self._popouts.get(run_id)
        if popout is not None:
            popout.append_line(line)

    def route_status(self, run_id: str, status: RunStatus) -> None:
        pane = self._panes.get(run_id)
        if pane is not None:
            pane.set_status(status)
        popout = self._popouts.get(run_id)
        if popout is not None:
            popout.set_status(status)

    # --- search / filter ---

    def _on_search_changed(self, _text: str) -> None:
        self._apply_filter()

    def _apply_filter(self) -> None:
        term = self._search.text().strip().lower()
        visible_count = 0
        for run_id, pane in self._panes.items():
            if self._maximized_id is not None and run_id != self._maximized_id:
                self._pane_shown[run_id] = False
                pane.setVisible(False)
                continue
            handle = self._vm.get_run(run_id)
            if handle is None:
                handle = pane._handle
            match = (
                not term
                or term in handle.cmd_name.lower()
                or term in handle.repo_name.lower()
            )
            self._pane_shown[run_id] = bool(match)
            pane.setVisible(bool(match))
            if match:
                visible_count += 1
        if term and visible_count == 0 and self._panes:
            self._no_match_label.setText(
                f'No running commands match "{self._search.text()}".'
            )
            self._no_match_label.setVisible(True)
        else:
            self._no_match_label.setVisible(False)

    # --- popout / maximize ---

    def _open_popout(self, run_id: str) -> None:
        from worktree_manager.ui.command_popout import CommandPopout
        existing = self._popouts.get(run_id)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        handle = self._vm.get_run(run_id)
        if not handle:
            return
        popout = CommandPopout(
            parent=self, handle=handle,
            on_stop=lambda: self._vm.stop(run_id),
            on_restart=lambda: self._do_restart(run_id),
            on_remove=lambda: self.remove_pane(run_id),
        )
        for line in handle.output_lines:
            popout.append_line(line)
        popout.set_status(handle.status)
        self._popouts[run_id] = popout
        popout.show()

    def maximize_pane(self, run_id: str) -> None:
        self._maximized_id = run_id
        self._apply_filter()

    def restore_tiled(self) -> None:
        self._maximized_id = None
        self._apply_filter()

    def is_maximized(self, run_id: str) -> bool:
        return self._maximized_id == run_id

    def is_visible(self, run_id: str) -> bool:
        return self._pane_shown.get(run_id, False)

    def empty_state_visible(self) -> bool:
        return not self._empty_label.isHidden()

    def trigger_close(self) -> None:
        self._on_close()

    def pane_count(self) -> int:
        return len(self._panes)

    def get_pane(self, run_id: str) -> CommandPane | None:
        return self._panes.get(run_id)

    # --- notifications toggle ---

    def _on_notif_toggled(self, checked: bool) -> None:
        self._vm._store.set_ui_pref("cmd_center_notifications_enabled", bool(checked))
        self._update_notif_btn()

    def _update_notif_btn(self) -> None:
        on = self._notif_btn.isChecked()
        self._notif_btn.setText("🔔" if on else "🔕")
        self._notif_btn.setToolTip(
            "Notifications: On — click to mute" if on
            else "Notifications: Off — click to enable"
        )

    # --- dialogs ---

    def _open_launch_dialog(self) -> None:
        dlg = LaunchDialog(parent=self, vm=self._vm)
        dlg.exec()

    def _open_manage_commands_dialog(self) -> None:
        dlg = ManageCommandsDialog(parent=self, vm=self._vm)
        dlg.exec()
